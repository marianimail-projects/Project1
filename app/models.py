from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_e164: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    guest_last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    property_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    booking_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    memory_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.utcnow(), onupdate=lambda: dt.datetime.utcnow()
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class HandoffRequest(Base):
    __tablename__ = "handoff_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_e164: Mapped[str] = mapped_column(String(32), index=True)
    guest_last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    property_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    booking_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_message: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())


class KBEntry(Base):
    __tablename__ = "kb_entries"
    __table_args__ = (UniqueConstraint("row_hash", name="uq_kb_row_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    row_hash: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(256), nullable=True)  # Appartamento / stanza
    scope: Mapped[str | None] = mapped_column(String(128), nullable=True)  # ambito
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str] = mapped_column(Text)
    embedding_json: Mapped[str] = mapped_column(Text)  # JSON list[float]

