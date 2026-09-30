"""API endpoints for Project management, conversational Q&A, and threads."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.chat.service import ChatService
from backend.app.db.session import get_db
from backend.app.repositories.conversation_repository import ConversationRepository
from backend.app.repositories.project_repository import ProjectRepository
from backend.app.retrieval.models import SearchFilter
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.conversation import ConversationResponse
from backend.app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter()


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project instance for codebase analysis."""
    repo = ProjectRepository(session)
    project = await repo.create(
        name=payload.name,
        source_type=payload.source_type,
        source_url=payload.source_url,
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List all projects",
)
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """Retrieve all projects with pagination."""
    repo = ProjectRepository(session)
    projects = await repo.list(skip=skip, limit=limit)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Retrieve details for a specific project."""
    repo = ProjectRepository(session)
    project = await repo.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/chat",
    response_model=ChatResponse,
    summary="Ask a question about the project codebase",
)
async def chat_with_codebase(
    project_id: uuid.UUID,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Ask a question about the codebase, returning a grounded answer and evidence references."""
    filters = None
    if payload.filters:
        filters = SearchFilter(
            language=payload.filters.language,
            file_path_pattern=payload.filters.file_path_pattern,
            chunk_types=payload.filters.chunk_types,
            symbol_name=payload.filters.symbol_name,
        )

    chat_service = ChatService(session=session)
    try:
        return await chat_service.ask_question(
            project_id=project_id,
            question=payload.message,
            conversation_id=payload.conversation_id,
            filters=filters,
            top_k=payload.top_k,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/{project_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation history",
)
async def get_conversation_history(
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Retrieve a conversation thread and its chronological messages."""
    repo = ConversationRepository(session)
    conv = await repo.get_with_messages(project_id, conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found for project '{project_id}'",
        )
    return ConversationResponse.model_validate(conv)


@router.get(
    "/{project_id}/conversations",
    response_model=list[ConversationResponse],
    summary="List conversations for a project",
)
async def list_project_conversations(
    project_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    """List all conversation threads associated with a project."""
    repo = ConversationRepository(session)
    conversations = await repo.list_by_project(project_id, skip=skip, limit=limit)
    return [ConversationResponse.model_validate(c) for c in conversations]
