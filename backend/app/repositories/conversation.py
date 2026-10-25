"""Reading and writing saved conversations."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.chat import Conversation, ConversationMessage


def create_conversation(db: Session, conversation_id: str, student_id: str, title: str) -> Conversation:
    conversation = Conversation(
        id=conversation_id, student_id=student_id, title=title or "New chat"
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, conversation_id: str, student_id: str | None = None) -> Conversation | None:
    query = select(Conversation).where(Conversation.id == conversation_id)
    if student_id:
        # A thread belongs to one student; never serve someone else's by id.
        query = query.where(Conversation.student_id == student_id)
    return db.scalar(query)


def list_conversations(db: Session, student_id: str, limit: int = 50) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.student_id == student_id, Conversation.archived.is_(False))
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
    )


def list_messages(db: Session, conversation_id: str) -> list[ConversationMessage]:
    return list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id)
        )
    )


def add_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    tool_used: str = "",
    source: str = "",
    provider: str = "",
    model: str = "",
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=conversation_id,
        role=role,
        content=content or "",
        tool_used=(tool_used or "")[:300],
        source=(source or "")[:120],
        provider=(provider or "")[:40],
        model=(model or "")[:80],
    )
    db.add(message)
    db.flush()
    return message


def touch_conversation(db: Session, conversation: Conversation) -> Conversation:
    """Recount the messages and mark the thread as just used."""
    conversation.message_count = db.scalar(
        select(func.count(ConversationMessage.id)).where(
            ConversationMessage.conversation_id == conversation.id
        )
    ) or 0
    db.commit()
    db.refresh(conversation)
    return conversation


def rename_conversation(db: Session, conversation: Conversation, title: str) -> Conversation:
    conversation.title = (title or "").strip()[:120] or "New chat"
    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation: Conversation) -> None:
    db.execute(
        delete(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation.id
        )
    )
    db.delete(conversation)
    db.commit()
