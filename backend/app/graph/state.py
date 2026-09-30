"""State model definitions for codebase analysis workflow in LangGraph."""

import operator
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

ApprovalStatus = Literal["pending", "approved", "feedback", "rejected"]


class CodebaseAnalysisState(TypedDict, total=False):
    """LangGraph execution state for codebase analysis and report generation."""

    project_id: str
    user_request: str
    conversation_id: str | None
    retrieved_evidence: list[dict[str, Any]]
    repository_summary: dict[str, Any]
    agent_results: dict[str, Any]
    report_draft: dict[str, Any] | str | None
    human_feedback: str | None
    approval_status: ApprovalStatus
    iteration: int
    max_iterations: int
    errors: Annotated[list[str], operator.add]
    final_report: dict[str, Any] | str | None


def create_initial_state(
    project_id: str,
    user_request: str = "Analyze codebase architecture, quality, and security.",
    conversation_id: str | None = None,
    max_iterations: int = 3,
) -> CodebaseAnalysisState:
    """Create a normalized initial state for a codebase analysis workflow."""
    return {
        "project_id": str(project_id),
        "user_request": user_request,
        "conversation_id": str(conversation_id) if conversation_id else None,
        "retrieved_evidence": [],
        "repository_summary": {},
        "agent_results": {},
        "report_draft": None,
        "human_feedback": None,
        "approval_status": "pending",
        "iteration": 1,
        "max_iterations": max_iterations,
        "errors": [],
        "final_report": None,
    }
