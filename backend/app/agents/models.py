"""Pydantic schemas for specialized codebase analysis agents."""

from typing import Any, Literal

from pydantic import BaseModel, Field

FindingSeverity = Literal["critical", "high", "medium", "low", "info"]


class Finding(BaseModel):
    """Structured code finding produced by specialized analysis agents."""

    title: str = Field(..., description="Short summary of finding")
    severity: FindingSeverity = Field(default="info", description="Severity rating")
    description: str = Field(..., description="Detailed description of finding")
    evidence: str = Field(..., description="Relevant code snippet or citation")
    file_path: str | None = Field(default=None, description="Target file path")
    start_line: int | None = Field(default=None, description="Starting line number")
    end_line: int | None = Field(default=None, description="Ending line number")
    recommendation: str = Field(..., description="Remediation or best practice guidance")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )


class BaseAgentResult(BaseModel):
    """Base model for structured agent analysis deliverables."""

    agent_name: str
    status: Literal["completed", "failed", "partial"] = "completed"
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExplorerResult(BaseAgentResult):
    """Structured output for ExplorerAgent."""

    overview: str = ""
    major_modules: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    configuration_files: list[str] = Field(default_factory=list)
    important_files: list[str] = Field(default_factory=list)


class ArchitectureResult(BaseAgentResult):
    """Structured output for ArchitectureAgent."""

    architectural_style: str = "Layered Architecture"
    major_components: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    data_flow: str = ""
    api_boundaries: list[str] = Field(default_factory=list)
    architectural_concerns: list[str] = Field(default_factory=list)


class SecurityResult(BaseAgentResult):
    """Structured output for SecurityAgent."""

    overall_posture: str = "Secure"
    positive_security_controls: list[str] = Field(default_factory=list)


class TestingQualityResult(BaseAgentResult):
    """Structured output for TestingQualityAgent."""

    test_frameworks: list[str] = Field(default_factory=list)
    test_coverage_indicators: str = ""
    missing_test_areas: list[str] = Field(default_factory=list)
    code_smells_and_maintainability: list[str] = Field(default_factory=list)
