"""Conversation and Message models for project-aware conversational Q&A."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from backend.app.models.project import Project


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Chat thread associated with a specific project."""

    __tablename__ = "conversations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Parent project ID for tenant isolation",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="New Conversation",
        nullable=False,
        doc="Display title of the conversation thread",
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} project_id={self.project_id} title='{self.title}'>"


class Message(Base, UUIDPrimaryKeyMixin):
    """Individual chat message within a conversation."""

    __tablename__ = "messages"

    __table_args__ = (Index("ix_messages_project_conversation", "project_id", "conversation_id"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Parent conversation thread ID",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Project ID for strict multi-tenant isolation",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Sender role: user, assistant, system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Text content of the message",
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Message metadata: cited chunk UUIDs, token counts, LLM model info",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
        doc="Message timestamp (timezone-aware UTC)",
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    project: Mapped["Project"] = relationship("Project")

    def __repr__(self) -> str:
        return f"<Message id={self.id} conversation_id={self.conversation_id} role='{self.role}'>"
