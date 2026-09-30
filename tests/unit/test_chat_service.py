"""Unit tests for ChatService prompt assembly, evidence formatting, and LLM mock."""

import uuid
from datetime import UTC, datetime

import pytest

from backend.app.chat.prompts import build_chat_messages, format_evidence_block
from backend.app.core.llm.factory import get_llm_provider
from backend.app.core.llm.mock_provider import MockLLMProvider
from backend.app.models.conversation import Message
from backend.app.retrieval.models import EvidenceChunk


def test_format_evidence_block_with_chunks():
    """Verify evidence block formats file paths, lines, and symbol metadata."""
    chunks = [
        EvidenceChunk(
            chunk_id="c1",
            file_path="src/security/auth.py",
            start_line=10,
            end_line=25,
            chunk_content="def verify_jwt(token: str): ...",
            score=0.95,
            match_type="semantic",
            symbol="verify_jwt",
            metadata={"language": "python"},
        ),
        EvidenceChunk(
            chunk_id="c2",
            file_path="src/api/routes.py",
            start_line=40,
            end_line=60,
            chunk_content="class AuthRouter: ...",
            score=0.85,
            match_type="lexical",
            symbol="AuthRouter",
            metadata={"language": "python"},
        ),
    ]

    block = format_evidence_block(chunks)
    assert "--- CODE EVIDENCE ---" in block
    assert "File: src/security/auth.py (Lines 10-25)" in block
    assert "Symbol: verify_jwt" in block
    assert "File: src/api/routes.py (Lines 40-60)" in block
    assert "Symbol: AuthRouter" in block


def test_format_evidence_block_empty():
    """Verify empty evidence block returns explicit insufficient notification."""
    block = format_evidence_block([])
    assert "No relevant code snippets were found in the project codebase." in block


def test_build_chat_messages_assembly():
    """Verify chat messages include system prompt, history, and latest user turn with evidence."""
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    history = [
        Message(
            id=uuid.uuid4(),
            project_id=pid,
            conversation_id=cid,
            role="user",
            content="Hello",
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid.uuid4(),
            project_id=pid,
            conversation_id=cid,
            role="assistant",
            content="Hi! Ask me anything about this codebase.",
            created_at=datetime.now(UTC),
        ),
    ]

    chunks = [
        EvidenceChunk(
            chunk_id="c1",
            file_path="config.py",
            start_line=1,
            end_line=10,
            chunk_content="DATABASE_URL = '...'",
            score=0.9,
            symbol="DATABASE_URL",
        )
    ]

    messages = build_chat_messages(
        history=history,
        evidence=chunks,
        user_question="Where is database configuration defined?",
    )

    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert "expert AI codebase analyst" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello"
    assert messages[2]["role"] == "assistant"
    assert messages[3]["role"] == "user"
    assert "--- CODE EVIDENCE ---" in messages[3]["content"]
    assert "File: config.py (Lines 1-10)" in messages[3]["content"]
    assert "User Question: Where is database configuration defined?" in messages[3]["content"]


@pytest.mark.asyncio
async def test_mock_llm_provider_evidence_citation():
    """Verify MockLLMProvider cites file paths and symbols from evidence."""
    provider = MockLLMProvider()
    messages = [
        {"role": "system", "content": "You are an assistant."},
        {
            "role": "user",
            "content": (
                "--- CODE EVIDENCE ---\n"
                "Snippet 1:\n"
                "File: src/auth.py (Lines 5-20)\n"
                "Symbol: authenticate_user\n"
                "Content:\n```python\ndef authenticate_user(): pass\n```\n"
                "---------------------\n\n"
                "User Question: where is authentication handled?"
            ),
        },
    ]

    answer = await provider.generate_response(messages)
    assert "[src/auth.py:5-20]" in answer
    assert "`authenticate_user`" in answer
    assert "is implemented at" in answer


@pytest.mark.asyncio
async def test_mock_llm_provider_insufficient_evidence():
    """Verify MockLLMProvider declares insufficient evidence when none is provided."""
    provider = MockLLMProvider()
    messages = [
        {"role": "system", "content": "You are an assistant."},
        {
            "role": "user",
            "content": (
                "No relevant code snippets were found in the project codebase.\n\n"
                "User Question: where is payment processing?"
            ),
        },
    ]

    answer = await provider.generate_response(messages)
    assert "does not contain sufficient information to answer this question" in answer


def test_llm_factory_mock():
    """Verify LLM factory returns MockLLMProvider when configured."""
    provider = get_llm_provider("mock", force_new=True)
    assert isinstance(provider, MockLLMProvider)
