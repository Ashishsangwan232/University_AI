"""Saved conversations, so a chat survives a page reload.

Two tables, deliberately plain:

    conversations           one thread, with a title and a rolling summary
    conversation_messages   every turn in it, in order

The summary is what keeps a long chat affordable. Rather than sending forty
turns to the model on every message, the recent turns go verbatim and everything
older is compressed once into ``summary`` - so the assistant still knows what
was discussed without paying for it again each time.

No UMS data is stored here. A message is what the student typed and what the
assistant replied; live figures are fetched fresh through the tools each time,
which is why an old thread never shows a stale attendance percentage as current.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), default="New chat", nullable=False)
    #: Everything older than the recent window, in a few sentences.
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    #: How many messages the summary already covers, so it is never redone.
    summarised_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.id",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: "user" or "assistant". Tool traffic is not replayed to the model - the
    #: tools are called again with current data instead.
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    #: Which tools produced the answer, for the message footer.
    tool_used: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
