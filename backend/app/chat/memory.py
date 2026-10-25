"""Conversation memory: what the assistant is told about what came before.

The problem this solves is the one you hit in every chat - having to repeat
context in each message. Now each thread is stored, and every question is sent
with the thread behind it.

The part that matters is the budget. Replaying forty turns on every message is
slow, expensive, and eventually exceeds the model's context. So:

    [rolling summary of everything older]  +  [the last N turns, verbatim]

The recent turns are exact, because that is where pronouns and follow-ups point
("and tomorrow?"). Everything before is compressed once into the summary and
never re-summarised, so the cost of a long chat stops growing.

Live data is deliberately NOT remembered. An answer that said "you are at 69%"
last week is kept as text, but the prompt tells the model that figures in the
history are historical, so it calls the tool again rather than repeating a stale
number as current.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import Conversation, ConversationMessage
from app.repositories.conversation import (
    add_message,
    create_conversation,
    get_conversation,
    list_messages,
    touch_conversation,
)

log = logging.getLogger("campusai.chat")

#: Prefixed to the history so the model treats old figures as old.
HISTORY_PREAMBLE = (
    "The exchange below is earlier in this same conversation with the student. "
    "Use it to understand what they are referring to - names, courses, dates and "
    "plans already discussed - so they do not have to repeat themselves. "
    "Any attendance percentages, timetables, notices or balances mentioned in it "
    "are from when they were asked: never repeat one as the current figure, call "
    "the tool again."
)

TITLE_NOISE = re.compile(r"^(hi|hey|hello|please|can you|could you|tell me|what is|whats|show me)\b[\s,]*", re.I)


def new_id() -> str:
    return uuid.uuid4().hex[:32]


def derive_title(first_message: str) -> str:
    """A thread title from the first question, without spending a model call.

    Titles are for scanning a list; a tidy prefix of the question does that as
    well as a generated one and costs nothing.
    """
    text = re.sub(r"\s+", " ", (first_message or "").strip())
    # "hey can you show me..." has two layers of politeness on it, so strip
    # until nothing more comes off.
    while True:
        trimmed = TITLE_NOISE.sub("", text).strip(" ?.!,")
        if trimmed == text:
            break
        text = trimmed
    if not text:
        return "New chat"
    words = text.split()
    title = " ".join(words[:8])
    if len(words) > 8:
        title += "…"
    return title[:120][:1].upper() + title[:120][1:]


def ensure_conversation(
    db: Session, conversation_id: str | None, student_id: str, first_message: str = ""
) -> Conversation:
    """Fetch the thread, or start one titled after the opening question."""
    if conversation_id:
        found = get_conversation(db, conversation_id, student_id)
        if found:
            return found
    return create_conversation(
        db, new_id(), student_id, derive_title(first_message)
    )


def _as_turn(message: ConversationMessage) -> dict[str, str]:
    role = "assistant" if message.role == "assistant" else "user"
    return {"role": role, "content": message.content}


def build_context(db: Session, conversation: Conversation) -> tuple[list[dict[str, str]], str]:
    """The prior turns to send, and the summary of everything older.

    Trims from the oldest end until the window fits the character budget, so one
    very long answer cannot push out the whole history.
    """
    messages = list_messages(db, conversation.id)
    if not messages:
        return [], conversation.summary or ""

    window = messages[-settings.chat_history_messages:]
    turns = [_as_turn(message) for message in window]

    budget = settings.chat_history_character_budget
    while turns and sum(len(turn["content"]) for turn in turns) > budget:
        turns.pop(0)

    # A single enormous answer would otherwise empty the window entirely.
    if not turns and window:
        last = _as_turn(window[-1])
        last["content"] = last["content"][:budget]
        turns = [last]

    return turns, conversation.summary or ""


def system_context(conversation: Conversation, turns: list[dict[str, str]]) -> str:
    """The one paragraph that carries older context into the prompt."""
    if not conversation.summary and not turns:
        return ""
    parts = [HISTORY_PREAMBLE]
    if conversation.summary:
        parts.append(f"Summary of the earlier part of this conversation: {conversation.summary}")
    return "\n\n".join(parts)


def record_exchange(
    db: Session,
    conversation: Conversation,
    question: str,
    answer: dict[str, Any],
) -> None:
    """Save the question and the answer, and retitle a brand-new thread."""
    add_message(db, conversation.id, "user", question)
    add_message(
        db,
        conversation.id,
        "assistant",
        answer.get("answer", ""),
        tool_used=answer.get("tool_used") or "",
        source=answer.get("source") or "",
        provider=answer.get("provider") or "",
        model=answer.get("model") or "",
    )
    if conversation.message_count <= 2 and conversation.title in ("", "New chat"):
        conversation.title = derive_title(question)
    touch_conversation(db, conversation)


def needs_summary(db: Session, conversation: Conversation) -> bool:
    total = conversation.message_count
    unsummarised = total - conversation.summarised_count
    return unsummarised > settings.chat_summary_after_messages


def summarise_older(db: Session, conversation: Conversation, summariser) -> bool:
    """Fold the older turns into the rolling summary.

    ``summariser`` takes a prompt and returns text - the same model that is
    answering. A failure here is not an error: the thread simply keeps its old
    summary and the recent window still works.
    """
    messages = list_messages(db, conversation.id)
    keep = settings.chat_history_messages
    older = messages[conversation.summarised_count:max(0, len(messages) - keep)]
    if not older:
        return False

    transcript = "\n".join(
        f"{'Student' if message.role == 'user' else 'CampusAI'}: {message.content[:800]}"
        for message in older
    )
    prompt = (
        "Summarise this part of a conversation between a university student and their "
        "assistant, in at most 120 words. Keep what the student is trying to do, any "
        "decisions or preferences they stated, and course codes, dates or names that "
        "later messages might refer back to. Do not keep attendance percentages, "
        "balances or other figures - those are looked up fresh each time. Write plain "
        "prose, no bullet points.\n\n"
        + (f"Summary so far: {conversation.summary}\n\n" if conversation.summary else "")
        + transcript
    )
    try:
        summary = (summariser(prompt) or "").strip()
    except Exception as exc:  # noqa: BLE001 - a failed summary must not fail the chat
        log.info("[chat] Could not summarise conversation %s: %s", conversation.id, exc)
        return False
    if not summary:
        return False

    conversation.summary = summary[:4000]
    conversation.summarised_count = conversation.summarised_count + len(older)
    db.commit()
    log.info("[chat] Summarised %d older message(s) in %s", len(older), conversation.id)
    return True
