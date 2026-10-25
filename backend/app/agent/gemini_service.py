"""Gemini, driving the shared CampusAI tool registry.

Everything specific to CampusAI - which tools exist, what they do, the system
instruction, how a tool result is turned into an intent and a source label -
lives in :mod:`app.agent.tools`. This file only knows how to talk to Gemini,
which is why adding a second provider did not mean duplicating any of it.
"""
from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.agent.tools import (
    SYSTEM_INSTRUCTION,
    TOOL_SPECS,
    execute_tool,
    intent_from_tools,
    source_from_tools,
)
from app.core.config import settings

#: Kept as an alias: older code and tests import this name.
TOOL_DECLARATIONS = TOOL_SPECS
log = logging.getLogger("campusai.agent")


class GeminiAgent:
    provider = "gemini"

    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model

    @staticmethod
    def available() -> bool:
        return bool(settings.gemini_api_key)

    def complete(self, prompt: str) -> str:
        """One plain completion, no tools. Used to summarise a long thread."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(temperature=0.2),
        )
        return response.text or ""

    def chat(
        self,
        message: str,
        student_id: str,
        db: Session,
        history: list[dict[str, str]] | None = None,
        context: str = "",
        effort: str | None = None,
    ) -> dict[str, Any]:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        # Earlier turns first, so follow-ups like "and tomorrow?" resolve.
        contents: list[Any] = [
            types.Content(
                role="model" if turn["role"] == "assistant" else "user",
                parts=[types.Part(text=turn["content"])],
            )
            for turn in (history or [])
        ]
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION + (f"\n\n{context}" if context else ""),
            tools=[types.Tool(function_declarations=TOOL_SPECS)],
            temperature=0.2,
        )

        if effort:
            config.thinking_config = types.ThinkingConfig(thinking_level=effort.upper())

        used_tools: list[str] = []
        live_used = False
        for _ in range(settings.agent_max_tool_rounds):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except Exception as exc:  # noqa: BLE001
                if config.thinking_config is None:
                    raise RuntimeError(f"Gemini is temporarily unavailable: {exc}") from exc
                # Older Gemini models take a thinking budget, not a level:
                # answer at the model's default rather than failing.
                log.info("[agent] gemini rejected thinking_level=%s: %s", effort, exc)
                config.thinking_config = None
                try:
                    response = self.client.models.generate_content(
                        model=self.model, contents=contents, config=config
                    )
                except Exception as retry_exc:  # noqa: BLE001
                    raise RuntimeError(f"Gemini is temporarily unavailable: {retry_exc}") from retry_exc

            candidate = response.candidates[0]
            contents.append(candidate.content)
            function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
            if not function_calls:
                return {
                    "answer": response.text or "I couldn't generate a response.",
                    "intent": intent_from_tools(used_tools),
                    "tool_used": " + ".join(used_tools) if used_tools else None,
                    "source": source_from_tools(used_tools, live_used),
                    "action": _action(used_tools),
                    "provider": self.provider,
                    "model": self.model,
                }

            function_parts = []
            for call in function_calls:
                name = call.name
                result = execute_tool(name, dict(call.args or {}), student_id, db)
                if isinstance(result, dict) and result.get("live"):
                    live_used = True
                used_tools.append(name)
                function_parts.append(
                    types.Part.from_function_response(name=name, response={"result": result})
                )
            contents.append(types.Content(role="user", parts=function_parts))

        raise RuntimeError("Gemini tool-calling loop exceeded the safety limit")


def _action(tools: list[str]) -> str | None:
    intent = intent_from_tools(tools)
    return None if intent == "general" else intent
