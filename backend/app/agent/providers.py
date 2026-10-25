"""Which model answers, and what happens when it cannot.

CampusAI can talk to more than one model. They share the tool registry in
:mod:`app.agent.tools`, so the choice only changes who writes the sentences -
never which data is available or how it is calculated.

Order of preference:

1. the provider the request asked for, if any;
2. otherwise ``AGENT_PROVIDER`` from .env (Ollama Cloud by default);
3. then the other configured provider, as a backup;
4. and if every model is unreachable, the deterministic local agent, which
   answers common questions from the same tools with no model at all.

Every answer says which model produced it, and a fallback is always reported
rather than hidden - if the model you picked did not answer, you find out.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agent.gemini_service import GeminiAgent
from app.agent.ollama_service import OllamaAgent
from app.core.config import settings

log = logging.getLogger("campusai.agent")

AGENTS = {"ollama": OllamaAgent, "gemini": GeminiAgent}
LABELS = {"ollama": "Ollama Cloud", "gemini": "Google Gemini"}


def _tidy(answer: str) -> str:
    """Clean model quirks: non-breaking hyphens and spaces break links, phone
    numbers and line wrapping, and some models leave markers like 【source】."""
    answer = answer.replace("‑", "-").replace("‐", "-")
    answer = answer.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s*【[^】]*】", "", answer)


def describe() -> dict[str, Any]:
    """What the Chat page shows in its model switcher."""
    return {
        "default": preferred(),
        "providers": [
            {
                "id": name,
                "label": LABELS[name],
                "model": settings.ollama_model if name == "ollama" else settings.gemini_model,
                "available": AGENTS[name].available(),
                "reason": "" if AGENTS[name].available() else _why_unavailable(name),
            }
            for name in AGENTS
        ],
    }


def _why_unavailable(name: str) -> str:
    if name == "ollama":
        return "Set OLLAMA_API_KEY in .env (get one from ollama.com), or point OLLAMA_BASE_URL at a local Ollama."
    return "Set GEMINI_API_KEY in .env."


def preferred() -> str:
    """The configured default, corrected if it is not actually usable."""
    choice = (settings.agent_provider or "ollama").strip().lower()
    if choice in AGENTS and AGENTS[choice].available():
        return choice
    for name, agent in AGENTS.items():
        if agent.available():
            return name
    return choice if choice in AGENTS else "ollama"


def order(requested: str | None = None) -> list[str]:
    """Providers to try, best first, without repeats."""
    wanted = (requested or "").strip().lower()
    sequence = []
    if wanted in AGENTS:
        sequence.append(wanted)
    sequence.append(preferred())
    if settings.agent_fallback:
        sequence.extend(AGENTS)
    seen: set[str] = set()
    return [name for name in sequence if not (name in seen or seen.add(name))]


def ask(
    message: str,
    student_id: str,
    db: Session,
    requested: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Answer with the best model that will actually respond.

    When a conversation is given, the thread's recent turns and its rolling
    summary go to the model with the question, and the exchange is saved - so
    the student never has to restate context they already gave.
    """
    from app.chat import memory

    attempts: list[dict[str, str]] = []
    conversation = memory.ensure_conversation(db, conversation_id, student_id, message)
    history, _ = memory.build_context(db, conversation)
    context = memory.system_context(conversation, history)

    for name in order(requested):
        agent_class = AGENTS[name]
        if not agent_class.available():
            attempts.append({"provider": name, "error": _why_unavailable(name)})
            continue
        try:
            agent = agent_class()
            result = agent.chat(message, student_id, db, history=history, context=context)
        except Exception as exc:  # noqa: BLE001 - any provider failure is a fallback reason
            log.warning("[agent] %s failed: %s", name, exc)
            attempts.append({"provider": name, "error": str(exc)})
            continue
        result["answer"] = _tidy(result.get("answer") or "")
        result["provider_label"] = LABELS.get(name, name)
        result["fell_back_from"] = attempts
        memory.record_exchange(db, conversation, message, result)
        # Compress the older turns once the thread outgrows the window, so a
        # long conversation does not get slower and dearer with every message.
        if memory.needs_summary(db, conversation):
            memory.summarise_older(db, conversation, agent.complete)
        result["conversation_id"] = conversation.id
        result["conversation_title"] = conversation.title
        result["history_turns"] = len(history)
        return result

    # No model answered. Rather than an error page, use the deterministic agent
    # that reads the same tools - and say plainly that no model was involved.
    from app.agent.service import answer as local_answer

    local = local_answer(message, student_id, db)
    note = "; ".join(f"{a['provider']}: {a['error']}" for a in attempts)
    fallback = {
        "answer": local.answer,
        "intent": local.intent,
        "tool_used": local.tool_used,
        "source": local.source,
        "action": local.action,
        "provider": "local",
        "provider_label": "CampusAI (no model)",
        "model": "rule-based",
        "fell_back_from": attempts,
        "note": f"No language model was reachable, so this is a direct lookup. {note}",
        "conversation_id": conversation.id,
        "conversation_title": conversation.title,
        "history_turns": len(history),
    }
    memory.record_exchange(db, conversation, message, fallback)
    return fallback
