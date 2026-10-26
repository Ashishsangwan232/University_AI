"""OpenAI, driving the shared CampusAI tool registry.

Uses the Chat Completions HTTP API directly (no extra package): same system
instruction, same tools and same dispatcher as Ollama and Gemini, so OpenAI
only changes who writes the sentences. Set OPENAI_API_KEY (and optionally
OPENAI_MODEL / OPENAI_BASE_URL) in .env.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.agent.tools import (
    SYSTEM_INSTRUCTION,
    TOOL_SPECS,
    execute_tool,
    intent_from_tools,
    source_from_tools,
)
from app.core.config import settings

log = logging.getLogger("campusai.agent")

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["parameters"],
        },
    }
    for spec in TOOL_SPECS
]


class OpenAIAgent:
    provider = "openai"

    def __init__(self) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.timeout = settings.openai_timeout_seconds
        self._effort_rejected = False

    @staticmethod
    def available() -> bool:
        return bool(settings.openai_api_key)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not reach OpenAI at {self.base_url}: {exc}") from exc

        if response.status_code == 401:
            raise RuntimeError("OpenAI rejected the API key (401). Check OPENAI_API_KEY in .env.")
        if response.status_code == 404:
            raise RuntimeError(
                f"OpenAI has no model called {self.model!r} for this key (404). Check OPENAI_MODEL in .env."
            )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI returned HTTP {response.status_code}: {response.text[:300]}")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"OpenAI returned a response that was not JSON: {exc}") from exc

    def _post_with_effort(self, payload: dict[str, Any], effort: str | None) -> dict[str, Any]:
        """Send with reasoning_effort; if this model does not take it, send without
        (and stop trying for the rest of this answer)."""
        if not effort or self._effort_rejected:
            return self._post(payload)
        try:
            return self._post({**payload, "reasoning_effort": effort})
        except RuntimeError as exc:
            if "reasoning_effort" not in str(exc):
                raise
            log.info("[agent] %s does not accept reasoning_effort; using its default", self.model)
            self._effort_rejected = True
            return self._post(payload)

    @staticmethod
    def _arguments(call: dict[str, Any]) -> dict[str, Any]:
        raw = (call.get("function") or {}).get("arguments")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def complete(self, prompt: str) -> str:
        """One plain completion, no tools. Used to summarise a long thread."""
        data = self._post({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        })
        choice = (data.get("choices") or [{}])[0]
        return ((choice.get("message") or {}).get("content") or "").strip()

    def chat(
        self,
        message: str,
        student_id: str,
        db: Session,
        history: list[dict[str, str]] | None = None,
        context: str = "",
        effort: str | None = None,
    ) -> dict[str, Any]:
        if not self.available():
            raise RuntimeError("OPENAI_API_KEY is not configured. Add it to .env.")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_INSTRUCTION + (f"\n\n{context}" if context else "")},
        ]
        messages.extend({"role": turn["role"], "content": turn["content"]} for turn in (history or []))
        messages.append({"role": "user", "content": message})
        used_tools: list[str] = []
        live_used = False

        for _ in range(settings.agent_max_tool_rounds):
            data = self._post_with_effort(
                {"model": self.model, "messages": messages, "tools": OPENAI_TOOLS}, effort
            )
            reply = ((data.get("choices") or [{}])[0].get("message")) or {}
            calls = reply.get("tool_calls") or []
            messages.append({
                "role": "assistant",
                "content": reply.get("content") or "",
                **({"tool_calls": calls} if calls else {}),
            })

            if not calls:
                answer = (reply.get("content") or "").strip()
                return {
                    "answer": answer or "I couldn't generate a response.",
                    "intent": intent_from_tools(used_tools),
                    "tool_used": " + ".join(used_tools) if used_tools else None,
                    "source": source_from_tools(used_tools, live_used),
                    "action": _action(used_tools),
                    "provider": self.provider,
                    "model": self.model,
                }

            for call in calls:
                name = ((call.get("function") or {}).get("name") or "").strip()
                result = execute_tool(name, self._arguments(call), student_id, db)
                if isinstance(result, dict) and result.get("live"):
                    live_used = True
                used_tools.append(name or "unknown_tool")
                log.info("[agent] openai called %s", name or "(unnamed)")
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(result, default=str)[:20000],
                })

        raise RuntimeError("The OpenAI tool-calling loop exceeded the safety limit")


def _action(tools: list[str]) -> str | None:
    intent = intent_from_tools(tools)
    return None if intent == "general" else intent
