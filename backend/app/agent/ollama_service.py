"""Ollama, driving the same CampusAI tool registry as Gemini.

Talks to Ollama Cloud by default::

    OLLAMA_BASE_URL=https://ollama.com
    OLLAMA_MODEL=gpt-oss:120b
    OLLAMA_API_KEY=...            # from https://ollama.com

and to a local daemon with no other change::

    OLLAMA_BASE_URL=http://localhost:11434
    OLLAMA_MODEL=gpt-oss:120b-cloud

Both speak the native ``/api/chat`` endpoint, which takes a ``tools`` list and
returns ``message.tool_calls``. Unlike the OpenAI shape, tool arguments come
back as a real object rather than a JSON string, and the tool result goes back
as a message with role ``tool``.

The API key is read from settings and sent only to the configured Ollama host.
No UMS credential ever reaches this file: the tools return data, never secrets.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

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

#: Hosts that are the student's own machine, where no API key is needed.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal", "::1")

#: Ollama's native tool shape wraps each declaration in a "function" envelope.
OLLAMA_TOOLS = [
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


class OllamaAgent:
    provider = "ollama"

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_seconds

    @staticmethod
    def available() -> bool:
        """A local daemon needs no key; a remote host - ollama.com - does."""
        url = (settings.ollama_base_url or "").strip()
        if not url:
            return False
        host = (urlparse(url).hostname or "").lower()
        if host in LOCAL_HOSTS:
            return True
        return bool(settings.ollama_api_key)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
        try:
            response = requests.post(
                f"{self.base_url}/api/chat", json=payload, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

        if response.status_code == 401:
            raise RuntimeError(
                "Ollama rejected the API key (401). Check OLLAMA_API_KEY in .env."
            )
        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama does not have a model called {self.model!r} at {self.base_url} (404). "
                "For Ollama Cloud use gpt-oss:120b; for a local daemon pull the model first."
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama returned a response that was not JSON: {exc}") from exc

    @staticmethod
    def _arguments(call: dict[str, Any]) -> dict[str, Any]:
        """Tool arguments, whichever shape the model produced.

        Ollama returns an object; some models still emit a JSON string. Neither
        is trusted enough to pass on unchecked - a bad shape becomes an empty
        argument set, and the tool reports what it needed.
        """
        raw = (call.get("function") or {}).get("arguments")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
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
            "stream": False,
            "options": {"temperature": 0.2},
        })
        return ((data.get("message") or {}).get("content") or "").strip()

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
            raise RuntimeError(
                "OLLAMA_API_KEY is not configured. Add a key from https://ollama.com to .env, "
                "or point OLLAMA_BASE_URL at a local Ollama."
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_INSTRUCTION + (f"\n\n{context}" if context else "")},
        ]
        # Earlier turns first, so follow-ups like "and tomorrow?" resolve.
        messages.extend(
            {"role": turn["role"], "content": turn["content"]} for turn in (history or [])
        )
        messages.append({"role": "user", "content": message})
        used_tools: list[str] = []
        live_used = False

        for _ in range(settings.agent_max_tool_rounds):
            data = self._post({
                "model": self.model,
                "messages": messages,
                "tools": OLLAMA_TOOLS,
                "stream": False,
                "options": {"temperature": 0.2},
                # gpt-oss takes a reasoning level: "low" / "medium" / "high".
                **({"think": effort} if effort else {}),
            })
            reply = data.get("message") or {}
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
                log.info("[agent] ollama called %s", name or "(unnamed)")
                messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": json.dumps(result, default=str)[:20000],
                })

        raise RuntimeError("The Ollama tool-calling loop exceeded the safety limit")


def _action(tools: list[str]) -> str | None:
    intent = intent_from_tools(tools)
    return None if intent == "general" else intent
