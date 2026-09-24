"""Unit tests for repository data access layer and project isolation enforcement."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.repositories import (
    ConversationRepository,
    FileRepository,
    ProjectRepository,
    ReportRepository,
    RepositoryRepository,
)


@pytest.mark.asyncio
async def test_project_repository_crud(db_session: AsyncSession):
    """Test ProjectRepository CRUD operations."""
    repo = ProjectRepository(db_session)
    unique_name = f"test-project-{uuid.uuid4().hex[:8]}"

    # Create
    project = await repo.create(
        name=unique_name,
        source_type="github",
        source_url="https://github.com/example/repo",
    )
    assert project.id is not None
    assert project.name == unique_name
    assert project.status == "created"

    # Get by ID and Name
    fetched = await repo.get_by_id(project.id)
    assert fetched is not None
    assert fetched.name == unique_name

    by_name = await repo.get_by_name(unique_name)
    assert by_name is not None
    assert by_name.id == project.id

    # Update Status
    updated = await repo.update_status(project.id, "ready")
    assert updated is not None
    assert updated.status == "ready"

    # Cleanup
    deleted = await repo.delete(project.id)
    assert deleted is True

    # Verify deleted
    assert await repo.get_by_id(project.id) is None


@pytest.mark.asyncio
async def test_strict_project_isolation(db_session: AsyncSession):
    """Verify that data belonging to Project A cannot be accessed or modified under Project B."""
    proj_repo = ProjectRepository(db_session)
    file_repo = FileRepository(db_session)
    repo_repo = RepositoryRepository(db_session)
    report_repo = ReportRepository(db_session)
    conv_repo = ConversationRepository(db_session)

    name_a = f"tenant-a-{uuid.uuid4().hex[:8]}"
    name_b = f"tenant-b-{uuid.uuid4().hex[:8]}"

    # Create two isolated projects
    proj_a = await proj_repo.create(name=name_a, source_type="github")
    proj_b = await proj_repo.create(name=name_b, source_type="github")

    try:
        # Create repository for Project A
        git_repo_a = await repo_repo.create_for_project(
            project_id=proj_a.id,
            name="org/repo-a",
            default_branch="main",
        )

        # Add File to Project A
        file_a = await file_repo.create(
            project_id=proj_a.id,
            repository_id=git_repo_a.id,
            path="src/index.ts",
            language="typescript",
            size=500,
            hash="abc111",
        )

        # Add Conversation and Message to Project A
        conv_a = await conv_repo.create_conversation(
            project_id=proj_a.id,
            title="Project A Chat",
        )
        await conv_repo.add_message(
            project_id=proj_a.id,
            conversation_id=conv_a.id,
            role="user",
            content="Hello Project A",
        )

        # Add Report to Project A
        report_a = await report_repo.create_report(
            project_id=proj_a.id,
            title="Report A",
            content_json={"score": 95},
        )

        # === VERIFY STRICT PROJECT ISOLATION ===

        # 1. Project B cannot fetch Project A's file
        assert await file_repo.get(proj_b.id, file_a.id) is None
        assert await file_repo.get_by_path(proj_b.id, "src/index.ts") is None
        assert len(await file_repo.list(proj_b.id)) == 0

        # 2. Project B cannot update or delete Project A's file
        assert await file_repo.update(proj_b.id, file_a.id, path="hacked.ts") is None
        assert await file_repo.delete(proj_b.id, file_a.id) is False

        # Verify file A was not modified
        unmodified_file_a = await file_repo.get(proj_a.id, file_a.id)
        assert unmodified_file_a is not None
        assert unmodified_file_a.path == "src/index.ts"

        # 3. Project B cannot view Project A's conversations or messages
        assert await conv_repo.get(proj_b.id, conv_a.id) is None
        assert await conv_repo.get_with_messages(proj_b.id, conv_a.id) is None
        assert len(await conv_repo.list_messages(proj_b.id, conv_a.id)) == 0

        # 4. Project B cannot add messages to Project A's conversation
        with pytest.raises(ValueError, match="not found for project"):
            await conv_repo.add_message(
                project_id=proj_b.id,
                conversation_id=conv_a.id,
                role="user",
                content="Cross-tenant intrusion attempt",
            )

        # 5. Project B cannot view or update Project A's report
        assert await report_repo.get(proj_b.id, report_a.id) is None
        assert await report_repo.get_latest_report(proj_b.id) is None
        assert (
            await report_repo.update_review_status(
                project_id=proj_b.id,
                report_id=report_a.id,
                status="approved",
            )
            is None
        )

    finally:
        # Cascade cleanup: deleting Project A removes all its children automatically
        await proj_repo.delete(proj_a.id)
        await proj_repo.delete(proj_b.id)
