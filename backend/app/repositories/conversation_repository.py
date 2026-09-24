"""Repository for managing Conversations and Messages."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.conversation import Conversation, Message
from backend.app.repositories.base import BaseProjectScopedRepository


class ConversationRepository(BaseProjectScopedRepository[Conversation]):
    """Data access repository for conversational Q&A threads and messages."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Conversation, session)

    async def get_with_messages(
        self,
        project_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Conversation | None:
        """Fetch a conversation with eagerly loaded messages."""
        stmt = (
            select(Conversation)
            .where(
                Conversation.project_id == project_id,
                Conversation.id == conversation_id,
            )
            .options(selectinload(Conversation.messages))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_conversation(
        self,
        project_id: uuid.UUID,
        title: str = "New Conversation",
    ) -> Conversation:
        """Create a new conversation thread bound to a project."""
        return await self.create(project_id=project_id, title=title)

    async def add_message(
        self,
        project_id: uuid.UUID,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> Message:
        """Add a message to a conversation ensuring strict project boundary verification."""
        # Ensure parent conversation belongs to the same project
        conv = await self.get(project_id, conversation_id)
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found for project {project_id}")

        msg = Message(
            project_id=project_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            meta=meta or {},
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def list_messages(
        self,
        project_id: uuid.UUID,
        conversation_id: uuid.UUID,
        limit: int = 100,
    ) -> list[Message]:
        """List messages chronologically for a project conversation."""
        stmt = (
            select(Message)
            .where(
                Message.project_id == project_id,
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
