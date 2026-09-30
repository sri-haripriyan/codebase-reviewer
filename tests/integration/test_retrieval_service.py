"""Integration tests for RetrievalService, project isolation, and metadata filtering."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.chunker.models import CodeChunk as DomainCodeChunk
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
from backend.app.retrieval.models import SearchFilter, SearchQuery
from backend.app.retrieval.service import RetrievalService


@pytest.fixture
def embedding_provider():
    """Deterministic 1536-d embedding provider for reproducible integration tests."""
    return DeterministicCodeEmbeddingProvider(dimension=1536)


@pytest.mark.asyncio
async def test_project_isolation(db_session: AsyncSession, embedding_provider):
    """Verify that retrieval strictly isolates projects and never leaks chunks across projects."""
    proj_repo = ProjectRepository(db_session)
    repo_repo = RepositoryRepository(db_session)
    file_repo = FileRepository(db_session)
    chunk_repo = CodeChunkRepository(db_session)

    proj_a = await proj_repo.create(name=f"project-a-{uuid.uuid4().hex[:6]}", source_type="github")
    proj_b = await proj_repo.create(name=f"project-b-{uuid.uuid4().hex[:6]}", source_type="github")

    try:
        # Project A setup: Auth logic
        repo_a = await repo_repo.create_for_project(project_id=proj_a.id, name="repo-a")
        file_a = await file_repo.create(
            project_id=proj_a.id,
            repository_id=repo_a.id,
            path="src/security/auth.py",
            language="python",
            size=500,
            hash="hash_a",
        )
        chunk_a = DomainCodeChunk(
            file_path="src/security/auth.py",
            language="python",
            content=(
                "def verify_jwt_token(token: str) -> bool:\n"
                "    # JWT signature verification\n"
                "    return decode_jwt(token)"
            ),
            start_line=1,
            end_line=5,
            chunk_type="function",
            symbol_name="verify_jwt_token",
        )

        # Project B setup: Payment logic
        repo_b = await repo_repo.create_for_project(project_id=proj_b.id, name="repo-b")
        file_b = await file_repo.create(
            project_id=proj_b.id,
            repository_id=repo_b.id,
            path="src/billing/payment.py",
            language="python",
            size=500,
            hash="hash_b",
        )
        chunk_b = DomainCodeChunk(
            file_path="src/billing/payment.py",
            language="python",
            content=(
                "def process_stripe_payment(amount: float):\n"
                "    # Stripe credit card billing\n"
                "    return stripe.charge(amount)"
            ),
            start_line=1,
            end_line=5,
            chunk_type="function",
            symbol_name="process_stripe_payment",
        )

        indexer = ChunkIndexerService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )
        await indexer.index_chunks(project_id=proj_a.id, file_id=file_a.id, chunks=[chunk_a])
        await indexer.index_chunks(project_id=proj_b.id, file_id=file_b.id, chunks=[chunk_b])

        retriever = RetrievalService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )

        # 1. Query Project A for JWT validation
        res_a = await retriever.search(
            SearchQuery(
                query="where is JWT validation performed?",
                project_id=proj_a.id,
                search_type="hybrid",
            )
        )
        assert res_a.total_found > 0
        assert any(e.symbol == "verify_jwt_token" for e in res_a.evidence)
        assert all(e.file_path == "src/security/auth.py" for e in res_a.evidence)

        # 2. Query Project B with Project A's exact query: MUST RETURN ZERO PROJECT A CHUNKS!
        res_b = await retriever.search(
            SearchQuery(
                query="where is JWT validation performed?",
                project_id=proj_b.id,
                search_type="hybrid",
            )
        )
        for evidence in res_b.evidence:
            assert evidence.file_path != "src/security/auth.py"
            assert evidence.symbol != "verify_jwt_token"

    finally:
        await proj_repo.delete(proj_a.id)
        await proj_repo.delete(proj_b.id)


@pytest.mark.asyncio
async def test_top_k_retrieval_and_evidence_format(db_session: AsyncSession, embedding_provider):
    """Verify top-k limit is respected and evidence contains all required fields."""
    proj_repo = ProjectRepository(db_session)
    repo_repo = RepositoryRepository(db_session)
    file_repo = FileRepository(db_session)
    chunk_repo = CodeChunkRepository(db_session)

    proj = await proj_repo.create(name=f"test-topk-{uuid.uuid4().hex[:6]}", source_type="zip")

    try:
        repo = await repo_repo.create_for_project(project_id=proj.id, name="repo-topk")
        file_db = await file_repo.create(
            project_id=proj.id,
            repository_id=repo.id,
            path="database/connection.py",
            language="python",
            size=600,
            hash="hash_db",
        )

        chunks = [
            DomainCodeChunk(
                file_path="database/connection.py",
                language="python",
                content="def get_database_connection():\n    return create_engine(DATABASE_URL)",
                start_line=1,
                end_line=5,
                chunk_type="function",
                symbol_name="get_database_connection",
            ),
            DomainCodeChunk(
                file_path="database/connection.py",
                language="python",
                content="def close_database_connection(conn):\n    conn.close()",
                start_line=7,
                end_line=10,
                chunk_type="function",
                symbol_name="close_database_connection",
            ),
            DomainCodeChunk(
                file_path="database/connection.py",
                language="python",
                content="def execute_query(sql: str):\n    return session.execute(sql)",
                start_line=12,
                end_line=16,
                chunk_type="function",
                symbol_name="execute_query",
            ),
            DomainCodeChunk(
                file_path="database/connection.py",
                language="python",
                content="def rollback_transaction():\n    session.rollback()",
                start_line=18,
                end_line=22,
                chunk_type="function",
                symbol_name="rollback_transaction",
            ),
        ]

        indexer = ChunkIndexerService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )
        await indexer.index_chunks(project_id=proj.id, file_id=file_db.id, chunks=chunks)

        retriever = RetrievalService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )

        # Request top_k=2
        res = await retriever.search(
            SearchQuery(
                query="database connection",
                project_id=proj.id,
                top_k=2,
                search_type="hybrid",
            )
        )

        assert res.total_found == 2
        # Check required evidence fields
        top = res.evidence[0]
        assert top.file_path == "database/connection.py"
        assert top.symbol in ("get_database_connection", "close_database_connection")
        assert top.start_line > 0
        assert top.end_line >= top.start_line
        assert top.line_range == (top.start_line, top.end_line)
        assert top.chunk_content
        assert top.score > 0.0
        assert top.match_type in ("hybrid", "semantic", "lexical")

        # Second chunk has score <= first chunk
        second = res.evidence[1]
        assert second.score <= top.score

    finally:
        await proj_repo.delete(proj.id)


@pytest.mark.asyncio
async def test_metadata_filtering(db_session: AsyncSession, embedding_provider):
    """Verify metadata filtering by language, chunk_type, file path, and symbol."""
    proj_repo = ProjectRepository(db_session)
    repo_repo = RepositoryRepository(db_session)
    file_repo = FileRepository(db_session)
    chunk_repo = CodeChunkRepository(db_session)

    proj = await proj_repo.create(name=f"test-filter-{uuid.uuid4().hex[:6]}", source_type="github")

    try:
        repo = await repo_repo.create_for_project(project_id=proj.id, name="repo-filter")

        # Python file
        f_py = await file_repo.create(
            project_id=proj.id,
            repository_id=repo.id,
            path="services/auth_service.py",
            language="python",
            size=300,
            hash="h_py",
        )
        # TypeScript file
        f_ts = await file_repo.create(
            project_id=proj.id,
            repository_id=repo.id,
            path="frontend/authClient.ts",
            language="typescript",
            size=300,
            hash="h_ts",
        )

        py_chunk = DomainCodeChunk(
            file_path="services/auth_service.py",
            language="python",
            content=(
                "def authenticate_credentials(user, password):\n    return verify(user, password)"
            ),
            start_line=1,
            end_line=5,
            chunk_type="function",
            symbol_name="authenticate_credentials",
        )
        ts_chunk = DomainCodeChunk(
            file_path="frontend/authClient.ts",
            language="typescript",
            content=(
                "export class AuthClient {\n    login(creds) { return http.post('/login'); }\n}"
            ),
            start_line=1,
            end_line=6,
            chunk_type="class",
            symbol_name="AuthClient",
        )

        indexer = ChunkIndexerService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )
        await indexer.index_chunks(project_id=proj.id, file_id=f_py.id, chunks=[py_chunk])
        await indexer.index_chunks(project_id=proj.id, file_id=f_ts.id, chunks=[ts_chunk])

        retriever = RetrievalService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )

        # 1. Filter by language = python
        res_py = await retriever.search(
            SearchQuery(
                query="authentication implementation",
                project_id=proj.id,
                filters=SearchFilter(language="python"),
            )
        )
        assert len(res_py.evidence) > 0
        assert all(e.file_path == "services/auth_service.py" for e in res_py.evidence)

        # 2. Filter by chunk_type = class
        res_class = await retriever.search(
            SearchQuery(
                query="authentication implementation",
                project_id=proj.id,
                filters=SearchFilter(chunk_types=["class"]),
            )
        )
        assert len(res_class.evidence) > 0
        assert all(e.symbol == "AuthClient" for e in res_class.evidence)

        # 3. Filter by file_path_pattern = frontend/
        res_path = await retriever.search(
            SearchQuery(
                query="authentication implementation",
                project_id=proj.id,
                filters=SearchFilter(file_path_pattern="frontend/"),
            )
        )
        assert len(res_path.evidence) > 0
        assert all("frontend/" in e.file_path for e in res_path.evidence)

        # 4. Filter by symbol_name = authenticate_credentials
        res_sym = await retriever.search(
            SearchQuery(
                query="authentication implementation",
                project_id=proj.id,
                filters=SearchFilter(symbol_name="authenticate_credentials"),
            )
        )
        assert len(res_sym.evidence) == 1
        assert res_sym.evidence[0].symbol == "authenticate_credentials"

    finally:
        await proj_repo.delete(proj.id)


@pytest.mark.asyncio
async def test_empty_results_handling(db_session: AsyncSession, embedding_provider):
    """Verify that querying empty projects or unmatched filters returns gracefully."""
    proj_repo = ProjectRepository(db_session)
    chunk_repo = CodeChunkRepository(db_session)

    empty_proj = await proj_repo.create(
        name=f"empty-proj-{uuid.uuid4().hex[:6]}",
        source_type="github",
    )

    try:
        retriever = RetrievalService(
            repository=chunk_repo,
            embedding_provider=embedding_provider,
        )

        res = await retriever.search(
            SearchQuery(
                query="payment processing with stripe",
                project_id=empty_proj.id,
                search_type="hybrid",
            )
        )
        assert res.total_found == 0
        assert res.evidence == []

        # Empty string query
        res_blank = await retriever.search(
            SearchQuery(
                query="",
                project_id=empty_proj.id,
            )
        )
        assert res_blank.total_found == 0
        assert res_blank.evidence == []

    finally:
        await proj_repo.delete(empty_proj.id)
