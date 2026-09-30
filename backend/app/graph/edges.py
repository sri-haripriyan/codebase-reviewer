"""Conditional routing logic and edge definitions for LangGraph workflow."""

from backend.app.core.logging import get_logger
from backend.app.graph.state import CodebaseAnalysisState

logger = get_logger(__name__)

ROUTE_FINALIZE = "finalize"
ROUTE_REVISE = "revise"

HUMAN_REVIEW_CONDITIONAL_TARGETS = {
    ROUTE_FINALIZE: "finalize",
    ROUTE_REVISE: "revise",
}


def route_human_review(state: CodebaseAnalysisState) -> str:
    """Evaluate human review decision and iteration limits to route the workflow.

    - If approval_status is 'approved': routes to 'finalize'.
    - If approval_status is 'feedback' / 'rejected' / 'revise' and iteration < max_iterations:
      routes to 'revise' to execute another analysis iteration.
    - If max_iterations is reached: routes to 'finalize' to avoid infinite loops.
    - Default fallback: 'finalize'.
    """
    approval = state.get("approval_status", "pending")
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 3)

    logger.info(
        "Routing review decision: approval_status='%s', iteration=%d/%d",
        approval,
        iteration,
        max_iterations,
    )

    if approval == "approved":
        return ROUTE_FINALIZE

    if approval in ("feedback", "rejected", "revise", "revision"):
        if iteration < max_iterations:
            return ROUTE_REVISE
        logger.warning(
            "Max iterations (%d) reached for project %s. Routing to finalize.",
            max_iterations,
            state.get("project_id"),
        )
        return ROUTE_FINALIZE

    # Fallback default if pending or unrecognized
    return ROUTE_FINALIZE
