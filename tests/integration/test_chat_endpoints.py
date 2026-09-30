"""Integration tests for Project creation, Chat endpoint, and Conversation history."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.chunker.models import CodeChunk as DomainCodeChunk
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.repositories import (
    CodeChunkRepository,
    FileRepository,
    ProjectRepository,
    RepositoryRepository,
)
from backend.app.retrieval.embeddings.deterministic_provider import (
    DeterministicCodeEmbeddingProvider,
)
from backend.app.retrieval.indexer import ChunkIndexerService


@pytest.fixture
def embedding_provider():
    """Deterministic 1536-d embedding provider."""
    return DeterministicCodeEmbeddingProvider(dimension=1536)


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    """Override FastAPI get_db dependency to use the test db_session."""

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_project_create_and_list(db_session: AsyncSession):
    """Verify POST /projects and GET /projects endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        proj_name = f"api-test-proj-{uuid.uuid4().hex[:6]}"
        resp = await ac.post(
            "/projects",
            json={
                "name": proj_name,
                "source_type": "github",
                "source_url": "https://github.com/org/repo",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == proj_name
        assert data["source_type"] == "github"
        assert "id" in data
        proj_id = data["id"]

        # List projects
        list_resp = await ac.get("/projects")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert any(p["id"] == proj_id for p in list_data)

        # Cleanup
        repo = ProjectRepository(db_session)
        await repo.delete(uuid.UUID(proj_id))


@pytest.mark.asyncio
async def test_chat_first_turn_and_evidence(db_session: AsyncSession, embedding_provider):
    """Verify POST /projects/{project_id}/chat seeds a thread and cites lines."""
    proj_repo = ProjectRepository(db_session)
    repo_repo = RepositoryRepository(db_session)
    file_repo = FileRepository(db_session)
    chunk_repo = CodeChunkRepository(db_session)

    proj = await proj_repo.create(name=f"chat-test-{uuid.uuid4().hex[:6]}", source_type="github")

    try:
        git_repo = await repo_repo.create_for_project(project_id=proj.id, name="repo-chat")
        f_auth = await file_repo.create(
            project_id=proj.id,
            repository_id=git_repo.id,
            path="src/security/jwt_auth.py",
            language="python",
            size=400,
            hash="h_auth",
        )

        chunk = DomainCodeChunk(
            file_path="src/security/jwt_auth.py",
            language="python",
            content=(
                "def validate_jwt_signature(token: str) -> dict:\n"
                "    # Validate signature against public key\n"
                "    return jwt.decode(token, key=PUBLIC_KEY, algorithms=['RS256'])"
            ),
            start_line=10,
            end_line=20,
            chunk_type="function",
            symbol_name="validate_jwt_signature",
        )

        indexer = ChunkIndexerService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )
        await indexer.index_chunks(project_id=proj.id, file_id=f_auth.id, chunks=[chunk])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            chat_resp = await ac.post(
                f"/projects/{proj.id}/chat",
                json={
                    "message": "where is JWT validation performed?",
                    "top_k": 3,
                },
            )
            assert chat_resp.status_code == 200
            data = chat_resp.json()

            assert "conversation_id" in data
            assert "answer" in data
            assert "evidence" in data
            assert len(data["evidence"]) > 0

            # Check evidence fields
            ev = data["evidence"][0]
            assert ev["file_path"] == "src/security/jwt_auth.py"
            assert ev["symbol"] == "validate_jwt_signature"
            assert ev["start_line"] == 10
            assert ev["end_line"] == 20
            assert ev["citation"] == "[src/security/jwt_auth.py:10-20]"

            # Check answer mentions symbol and citation
            answer = data["answer"]
            assert "[src/security/jwt_auth.py:10-20]" in answer
            assert "validate_jwt_signature" in answer

    finally:
        await proj_repo.delete(proj.id)


@pytest.mark.asyncio
async def test_chat_multi_turn_and_conversation_history(
    db_session: AsyncSession, embedding_provider
):
    """Verify continuing a conversation with conversation_id and fetching history via GET."""
    proj_repo = ProjectRepository(db_session)
    repo_repo = RepositoryRepository(db_session)
    file_repo = FileRepository(db_session)
    chunk_repo = CodeChunkRepository(db_session)

    proj = await proj_repo.create(name=f"multi-turn-{uuid.uuid4().hex[:6]}", source_type="github")

    try:
        git_repo = await repo_repo.create_for_project(project_id=proj.id, name="repo-multi")
        f_db = await file_repo.create(
            project_id=proj.id,
            repository_id=git_repo.id,
            path="database/pool.py",
            language="python",
            size=300,
            hash="h_pool",
        )
        chunk = DomainCodeChunk(
            file_path="database/pool.py",
            language="python",
            content="def init_connection_pool(): return create_pool()",
            start_line=1,
            end_line=5,
            chunk_type="function",
            symbol_name="init_connection_pool",
        )

        indexer = ChunkIndexerService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )
        await indexer.index_chunks(project_id=proj.id, file_id=f_db.id, chunks=[chunk])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Turn 1: Initial question
            resp1 = await ac.post(
                f"/projects/{proj.id}/chat",
                json={"message": "how is the database connection pool initialized?"},
            )
            assert resp1.status_code == 200
            data1 = resp1.json()
            conv_id = data1["conversation_id"]

            # Turn 2: Follow-up question in the same conversation
            resp2 = await ac.post(
                f"/projects/{proj.id}/chat",
                json={
                    "message": "what function was that again?",
                    "conversation_id": conv_id,
                },
            )
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["conversation_id"] == conv_id

            # Turn 3: Fetch conversation history via GET endpoint
            hist_resp = await ac.get(f"/projects/{proj.id}/conversations/{conv_id}")
            assert hist_resp.status_code == 200
            hist_data = hist_resp.json()
            assert hist_data["id"] == conv_id
            assert hist_data["project_id"] == str(proj.id)

            messages = hist_data["messages"]
            # Should have 4 messages: Turn 1 (user, asst) + Turn 2 (user, asst)
            assert len(messages) == 4
            assert messages[0]["role"] == "user"
            assert "database connection pool" in messages[0]["content"]
            assert messages[1]["role"] == "assistant"
            assert messages[2]["role"] == "user"
            assert messages[3]["role"] == "assistant"

    finally:
        await proj_repo.delete(proj.id)


@pytest.mark.asyncio
async def test_project_isolation_in_chat(db_session: AsyncSession):
    """Verify that a conversation from Project A cannot be accessed or continued from Project B."""
    proj_repo = ProjectRepository(db_session)

    proj_a = await proj_repo.create(name=f"proj-a-{uuid.uuid4().hex[:6]}", source_type="github")
    proj_b = await proj_repo.create(name=f"proj-b-{uuid.uuid4().hex[:6]}", source_type="github")

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Create conversation in Project A
            resp_a = await ac.post(
                f"/projects/{proj_a.id}/chat",
                json={"message": "hello project A"},
            )
            assert resp_a.status_code == 200
            conv_a_id = resp_a.json()["conversation_id"]

            # Attempt to chat in Project B using Project A's conversation ID -> 404
            resp_cross = await ac.post(
                f"/projects/{proj_b.id}/chat",
                json={"message": "hijack conversation", "conversation_id": conv_a_id},
            )
            assert resp_cross.status_code == 404
            assert "not found" in resp_cross.json()["detail"].lower()

            # Attempt to GET Project A's conversation from Project B -> 404
            get_cross = await ac.get(f"/projects/{proj_b.id}/conversations/{conv_a_id}")
            assert get_cross.status_code == 404

    finally:
        await proj_repo.delete(proj_a.id)
        await proj_repo.delete(proj_b.id)


@pytest.mark.asyncio
async def test_chat_insufficient_evidence(db_session: AsyncSession):
    """Verify that assistant clearly states when codebase evidence is insufficient."""
    proj_repo = ProjectRepository(db_session)
    empty_proj = await proj_repo.create(name=f"empty-{uuid.uuid4().hex[:6]}", source_type="github")

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"/projects/{empty_proj.id}/chat",
                json={"message": "where is the Stripe webhook handler?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["evidence"] == []
            assert "does not contain sufficient information" in data["answer"]

    finally:
        await proj_repo.delete(empty_proj.id)
