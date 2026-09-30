"""Unit tests for specialized codebase analysis agents."""

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from backend.app.agents.architecture import ArchitectureAgent
from backend.app.agents.explorer import ExplorerAgent
from backend.app.agents.models import Finding
from backend.app.agents.security import SecurityAgent
from backend.app.agents.testing_quality import TestingQualityAgent
from backend.app.core.llm.mock_provider import MockLLMProvider
from backend.app.retrieval.models import EvidenceChunk, RetrievalResult


def test_finding_model_validation():
    """Verify Finding model validates required fields, severity, and confidence bounds."""
    finding = Finding(
        title="Hardcoded API key detected",
        severity="critical",
        description="Private secret found in configuration file.",
        evidence="api_key = 'sk-12345'",
        file_path="src/config.py",
        start_line=12,
        end_line=12,
        recommendation="Move key to environment variable.",
        confidence=0.98,
    )
    assert finding.title == "Hardcoded API key detected"
    assert finding.severity == "critical"
    assert finding.confidence == 0.98

    # Invalid severity raises ValidationError
    with pytest.raises(ValidationError):
        Finding(
            title="Invalid finding",
            severity="extreme",  # type: ignore
            description="desc",
            evidence="code",
            recommendation="rec",
        )

    # Invalid confidence bounds raise ValidationError
    with pytest.raises(ValidationError):
        Finding(
            title="Out of bounds",
            description="desc",
            evidence="code",
            recommendation="rec",
            confidence=1.5,
        )


@pytest.mark.asyncio
async def test_explorer_agent_analysis():
    """Verify ExplorerAgent discovers modules, entrypoints, and config files."""
    llm = MockLLMProvider()
    agent = ExplorerAgent(llm_provider=llm)

    result = await agent.analyze(project_id="proj-exp-1", user_request="Explore repository")

    assert result.agent_name == "ExplorerAgent"
    assert result.status == "completed"
    assert len(result.major_modules) > 0
    assert "backend/app/main.py" in result.entry_points
    assert any("config" in cfg for cfg in result.configuration_files)
    assert len(result.findings) >= 1
    assert result.findings[0].file_path == "backend/app/main.py"


@pytest.mark.asyncio
async def test_architecture_agent_analysis():
    """Verify ArchitectureAgent identifies style, components, data flow, and boundaries."""
    llm = MockLLMProvider()
    agent = ArchitectureAgent(llm_provider=llm)

    result = await agent.analyze(project_id="proj-arch-1", user_request="Review architecture")

    assert result.agent_name == "ArchitectureAgent"
    assert result.status == "completed"
    assert "Layered" in result.architectural_style
    assert len(result.major_components) >= 2
    assert "HTTP Request" in result.data_flow
    assert len(result.api_boundaries) >= 1
    assert len(result.findings) >= 1


@pytest.mark.asyncio
async def test_security_agent_analysis_and_evidence_rule():
    """Verify SecurityAgent reports security posture and enforces evidence verification."""
    llm = MockLLMProvider()
    agent = SecurityAgent(llm_provider=llm)

    result = await agent.analyze(project_id="proj-sec-1", user_request="Audit security")

    assert result.agent_name == "SecurityAgent"
    assert result.status == "completed"
    assert len(result.positive_security_controls) >= 1
    assert any("SQLAlchemy" in ctrl for ctrl in result.positive_security_controls)
    assert len(result.findings) >= 1


@pytest.mark.asyncio
async def test_security_agent_downgrades_unevidenced_vulnerabilities():
    """Verify SecurityAgent strictly downgrades claims lacking code evidence to info."""
    # LLM hallucinates a 'critical' claim with no evidence snippet or file path
    hallucinated_json = json.dumps(
        {
            "agent_name": "SecurityAgent",
            "status": "completed",
            "summary": "Audit with unverified claim",
            "overall_posture": "At Risk",
            "positive_security_controls": [],
            "findings": [
                {
                    "title": "Suspected remote code execution",
                    "severity": "critical",
                    "description": "System might allow RCE through dynamic code execution.",
                    "evidence": "",  # Missing evidence
                    "file_path": None,  # Missing file
                    "recommendation": "Review all eval statements.",
                    "confidence": 0.5,
                }
            ],
        }
    )

    llm = MockLLMProvider(fixed_response=hallucinated_json)
    agent = SecurityAgent(llm_provider=llm)

    result = await agent.analyze(project_id="proj-sec-2")

    # Claim must be downgraded to 'info' because no evidence was provided
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.severity == "info"
    assert "[Unverified - missing code evidence]" in finding.description


@pytest.mark.asyncio
async def test_testing_quality_agent_analysis():
    """Verify TestingQualityAgent detects test frameworks, coverage, and smells."""
    llm = MockLLMProvider()
    agent = TestingQualityAgent(llm_provider=llm)

    result = await agent.analyze(project_id="proj-test-1", user_request="Audit test coverage")

    assert result.agent_name == "TestingQualityAgent"
    assert result.status == "completed"
    assert "pytest" in result.test_frameworks
    assert len(result.findings) >= 1
    assert "conftest.py" in (result.findings[0].file_path or "")


@pytest.mark.asyncio
async def test_agent_uses_retrieval_service_queries():
    """Verify agent uses RetrievalService to fetch code evidence instead of full repo."""
    pid = "00000000-0000-0000-0000-000000000001"
    mock_retrieval = AsyncMock()
    mock_retrieval.search.return_value = RetrievalResult(
        query="dummy",
        project_id=uuid.UUID(pid),
        evidence=[
            EvidenceChunk(
                chunk_id="chk-101",
                file_path="src/auth.py",
                start_line=1,
                end_line=15,
                chunk_content="def authenticate(user, pwd): ...",
                score=0.92,
                symbol="authenticate",
            )
        ],
        total_found=1,
        search_type="hybrid",
    )

    llm = MockLLMProvider()
    agent = SecurityAgent(llm_provider=llm, retrieval_service=mock_retrieval)
    await agent.analyze(project_id=pid)

    # Verify retrieval was invoked for domain queries
    assert mock_retrieval.search.call_count >= 1
    # Verify the chunk was formatted into the prompt sent to LLM
    assert len(llm.recorded_calls) >= 1
    user_call_content = llm.recorded_calls[0][1]["content"]
    assert "src/auth.py" in user_call_content
    assert "authenticate" in user_call_content
