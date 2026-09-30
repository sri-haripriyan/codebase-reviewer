"""ChatService orchestrating code retrieval, prompt construction, and conversation persistence."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.chat.prompts import build_chat_messages
from backend.app.core.llm.base import BaseLLMProvider
from backend.app.core.llm.factory import get_llm_provider
from backend.app.core.logging import get_logger
from backend.app.repositories.code_chunk_repository import CodeChunkRepository
from backend.app.repositories.conversation_repository import ConversationRepository
from backend.app.repositories.project_repository import ProjectRepository
from backend.app.retrieval.models import SearchFilter
from backend.app.retrieval.service import RetrievalService
from backend.app.schemas.chat import ChatResponse, EvidenceReference

logger = get_logger(__name__)


class ChatService:
    """Project-aware conversational assistant adhering to grounded evidence."""

    def __init__(
        self,
        session: AsyncSession,
        retrieval_service: RetrievalService | None = None,
        llm_provider: BaseLLMProvider | None = None,
    ) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.conv_repo = ConversationRepository(session)
        chunk_repo = CodeChunkRepository(session)
        self.retrieval_service = retrieval_service or RetrievalService(repository=chunk_repo)
        self.llm_provider = llm_provider or get_llm_provider()

    async def ask_question(
        self,
        project_id: uuid.UUID,
        question: str,
        conversation_id: uuid.UUID | None = None,
        filters: SearchFilter | None = None,
        top_k: int = 5,
    ) -> ChatResponse:
        """Answer user questions grounded strictly in project code evidence."""
        # 1. Enforce project existence and tenant boundary
        project = await self.project_repo.get(project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found")

        # 2. Get or create conversation thread
        if conversation_id is not None:
            conv = await self.conv_repo.get(project_id, conversation_id)
            if not conv:
                raise ValueError(
                    f"Conversation '{conversation_id}' not found for project '{project_id}'"
                )
        else:
            title = question.strip()[:60] + ("..." if len(question.strip()) > 60 else "")
            conv = await self.conv_repo.create_conversation(project_id, title=title)
            conversation_id = conv.id

        # 3. Retrieve relevant code evidence (strictly scoped to project_id)
        evidence_chunks = await self.retrieval_service.hybrid_search(
            project_id=project_id,
            query=question,
            top_k=top_k,
            filters=filters,
        )

        # 4. Fetch prior conversation history
        history = await self.conv_repo.list_messages(project_id, conversation_id, limit=10)

        # 5. Assemble prompt with grounded evidence
        messages = build_chat_messages(
            history=history,
            evidence=evidence_chunks,
            user_question=question,
        )

        # 6. Generate LLM response
        answer = await self.llm_provider.generate_response(messages)

        # 7. Convert evidence chunks to structured reference models
        evidence_refs: list[EvidenceReference] = [
            EvidenceReference(
                file_path=chunk.file_path,
                symbol=chunk.symbol,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.chunk_content,
                score=chunk.score,
                citation=f"[{chunk.file_path}:{chunk.start_line}-{chunk.end_line}]",
                metadata=chunk.metadata,
            )
            for chunk in evidence_chunks
        ]

        # 8. Persist conversation turn to PostgreSQL
        await self.conv_repo.add_message(
            project_id=project_id,
            conversation_id=conversation_id,
            role="user",
            content=question,
        )

        asst_msg = await self.conv_repo.add_message(
            project_id=project_id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            meta={
                "cited_chunks": [c.chunk_id for c in evidence_chunks],
                "evidence_count": len(evidence_chunks),
            },
        )

        logger.info(
            "Answered question for project %s in conversation %s (cited %d chunks)",
            project_id,
            conversation_id,
            len(evidence_refs),
        )

        return ChatResponse(
            conversation_id=conversation_id,
            message_id=asst_msg.id,
            answer=answer,
            evidence=evidence_refs,
            created_at=asst_msg.created_at,
        )
