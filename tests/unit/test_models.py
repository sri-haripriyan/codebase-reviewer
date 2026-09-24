"""Unit tests for SQLAlchemy domain models."""

import uuid

from backend.app.core.config import settings
from backend.app.models import (
    CodeChunk,
    Conversation,
    File,
    Message,
    Project,
    Report,
    Repository,
)


def test_project_model_instantiation():
    """Verify Project model fields and UUID defaults."""
    project = Project(
        name="test-repo",
        source_type="github",
        source_url="https://github.com/example/test-repo",
    )
    assert project.name == "test-repo"
    assert project.source_type == "github"
    assert project.status == "created"
    assert "test-repo" in repr(project)


def test_repository_model_instantiation():
    """Verify Repository model fields and project_id binding."""
    project_id = uuid.uuid4()
    repo = Repository(
        project_id=project_id,
        name="example/test-repo",
        default_branch="main",
        commit_sha="abc123456",
        meta={"stars": 42, "language": "Python"},
    )
    assert repo.project_id == project_id
    assert repo.name == "example/test-repo"
    assert repo.default_branch == "main"
    assert repo.commit_sha == "abc123456"
    assert repo.meta["stars"] == 42


def test_file_model_instantiation():
    """Verify File model fields."""
    project_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    f = File(
        project_id=project_id,
        repository_id=repo_id,
        path="backend/main.py",
        language="python",
        size=1024,
        hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert f.project_id == project_id
    assert f.repository_id == repo_id
    assert f.path == "backend/main.py"
    assert f.language == "python"


def test_code_chunk_model_embedding_dimension():
    """Verify CodeChunk embedding dimension is parameterized from settings."""
    project_id = uuid.uuid4()
    file_id = uuid.uuid4()
    chunk = CodeChunk(
        project_id=project_id,
        file_id=file_id,
        content="def hello(): pass",
        start_line=1,
        end_line=1,
        chunk_type="function",
        symbol_name="hello",
    )
    assert chunk.project_id == project_id
    assert chunk.file_id == file_id
    assert chunk.chunk_type == "function"

    # Verify vector column dimension
    vector_col = CodeChunk.__table__.c.embedding
    assert vector_col.type.dim == settings.EMBEDDING_DIMENSION
    assert vector_col.type.dim == 1536


def test_conversation_and_message_models():
    """Verify Conversation and Message model structure."""
    project_id = uuid.uuid4()
    conv = Conversation(project_id=project_id, title="Architecture Discussion")
    assert conv.project_id == project_id
    assert conv.title == "Architecture Discussion"

    conv_id = uuid.uuid4()
    msg = Message(
        project_id=project_id,
        conversation_id=conv_id,
        role="user",
        content="Explain the auth flow",
        meta={"tokens": 12},
    )
    assert msg.project_id == project_id
    assert msg.conversation_id == conv_id
    assert msg.role == "user"
    assert msg.meta["tokens"] == 12


def test_report_model():
    """Verify Report model versioning and status fields."""
    project_id = uuid.uuid4()
    report = Report(
        project_id=project_id,
        title="Comprehensive Code Review",
        version=1,
        status="pending_review",
        content_json={"summary": "All checks passed"},
    )
    assert report.project_id == project_id
    assert report.version == 1
    assert report.status == "pending_review"
    assert report.content_json["summary"] == "All checks passed"
