"""OpenAI, driving the shared CampusAI tool registry.

Uses the Responses API (/v1/responses) over plain HTTP - no extra package.
Newer models such as gpt-6-luna refuse function tools together with a
reasoning effort on /v1/chat/completions; the Responses API supports both.

Requests are stateless (store=false): OpenAI does not keep the student's UMS
data between calls. Each round sends back the previous output items, with the
model's reasoning carried as encrypted content, which is how the Responses API
works without server-side storage.

Same system instruction, tools and dispatcher as Ollama and Gemini, so OpenAI
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

#: The Responses API takes function tools flat, not wrapped in "function".
OPENAI_TOOLS = [
    {
        "type": "function",
        "name": spec["name"],
        "description": spec["description"],
        "parameters": spec["parameters"],
    }
    for spec in TOOL_SPECS
]


class OpenAIAgent:
    provider = "openai"

    def __init__(self) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.timeout = settings.openai_timeout_seconds
        # Some models take no reasoning settings at all; learnt per answer.
        self._reasoning_rejected = False

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
                f"{self.base_url}/responses", json=payload, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not reach OpenAI at {self.base_url}: {exc}") from exc

        if response.status_code == 401:
            raise RuntimeError("OpenAI rejected the API key (401). Check OPENAI_API_KEY in .env.")
        if response.status_code == 404:
            raise RuntimeError(
                f"OpenAI has no model called {self.model!r} for this key (404). Check OPENAI_MODEL in .env."
            )
        if response.status_code == 429:
            raise RuntimeError(f"OpenAI rate limit or quota reached (429): {response.text[:300]}")
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI returned HTTP {response.status_code}: {response.text[:400]}")
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"OpenAI returned a response that was not JSON: {exc}") from exc
        if data.get("status") == "failed" or data.get("error"):
            raise RuntimeError(f"OpenAI could not complete the answer: {data.get('error')}")
        return data

    def _send(self, payload: dict[str, Any], effort: str | None) -> dict[str, Any]:
        """Send with the reasoning effort and encrypted reasoning carried along;
        a model that takes no reasoning settings gets the request without them."""
        if not self._reasoning_rejected:
            reasoning_payload = {
                **payload,
                "reasoning": {"effort": effort} if effort else {},
                "include": ["reasoning.encrypted_content"],
            }
            try:
                return self._post(reasoning_payload)
            except RuntimeError as exc:
                if "reasoning" not in str(exc):
                    raise
                log.info("[agent] %s takes no reasoning settings; using its default", self.model)
                self._reasoning_rejected = True
        return self._post(payload)

    @staticmethod
    def _text(data: dict[str, Any]) -> str:
        parts = []
        for item in data.get("output") or []:
            if item.get("type") == "message":
                for part in item.get("content") or []:
                    if part.get("type") == "output_text":
                        parts.append(part.get("text") or "")
        return "".join(parts).strip()

    @staticmethod
    def _arguments(raw: Any) -> dict[str, Any]:
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
        data = self._send({"model": self.model, "input": prompt, "store": False}, "low")
        return self._text(data)

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

        instructions = SYSTEM_INSTRUCTION + (f"\n\n{context}" if context else "")
        # Earlier turns first, so follow-ups like "and tomorrow?" resolve.
        items: list[dict[str, Any]] = [
            {"role": turn["role"], "content": turn["content"]} for turn in (history or [])
        ]
        items.append({"role": "user", "content": message})
        used_tools: list[str] = []
        live_used = False

        for _ in range(settings.agent_max_tool_rounds):
            data = self._send(
                {
                    "model": self.model,
                    "instructions": instructions,
                    "input": items,
                    "tools": OPENAI_TOOLS,
                    "store": False,
                },
                effort,
            )
            output = data.get("output") or []
            calls = [item for item in output if item.get("type") == "function_call"]

            if not calls:
                answer = self._text(data)
                return {
                    "answer": answer or "I couldn't generate a response.",
                    "intent": intent_from_tools(used_tools),
                    "tool_used": " + ".join(used_tools) if used_tools else None,
                    "source": source_from_tools(used_tools, live_used),
                    "action": _action(used_tools),
                    "provider": self.provider,
                    "model": self.model,
                }

            # Send this round's output back (reasoning included) with the results.
            items.extend(output)
            for call in calls:
                name = (call.get("name") or "").strip()
                result = execute_tool(name, self._arguments(call.get("arguments")), student_id, db)
                if isinstance(result, dict) and result.get("live"):
                    live_used = True
                used_tools.append(name or "unknown_tool")
                log.info("[agent] openai called %s", name or "(unnamed)")
                items.append({
                    "type": "function_call_output",
                    "call_id": call.get("call_id", ""),
                    "output": json.dumps(result, default=str)[:20000],
                })

        raise RuntimeError("The OpenAI tool-calling loop exceeded the safety limit")


def _action(tools: list[str]) -> str | None:
    intent = intent_from_tools(tools)
    return None if intent == "general" else intent
