"""Unit tests for LangGraph CodebaseAnalysisState and initial state factory."""

import uuid

from backend.app.graph.state import CodebaseAnalysisState, create_initial_state


def test_create_initial_state_defaults():
    """Verify create_initial_state populates all required conceptual fields with defaults."""
    pid = str(uuid.uuid4())
    state = create_initial_state(project_id=pid)

    assert state["project_id"] == pid
    assert "Analyze codebase architecture" in state["user_request"]
    assert state["conversation_id"] is None
    assert state["retrieved_evidence"] == []
    assert state["repository_summary"] == {}
    assert state["agent_results"] == {}
    assert state["report_draft"] is None
    assert state["human_feedback"] is None
    assert state["approval_status"] == "pending"
    assert state["iteration"] == 1
    assert state["max_iterations"] == 3
    assert state["errors"] == []
    assert state["final_report"] is None


def test_create_initial_state_custom_params():
    """Verify custom parameters for user request, conversation, and max iterations."""
    pid = "proj-xyz"
    cid = "conv-abc"
    request = "Focus on OWASP Top 10 vulnerabilities."
    state = create_initial_state(
        project_id=pid,
        user_request=request,
        conversation_id=cid,
        max_iterations=5,
    )

    assert state["project_id"] == pid
    assert state["user_request"] == request
    assert state["conversation_id"] == cid
    assert state["max_iterations"] == 5
    assert state["iteration"] == 1


def test_state_typed_dict_compatibility():
    """Verify CodebaseAnalysisState can be instantiated with partial fields."""
    partial: CodebaseAnalysisState = {
        "project_id": "test-p1",
        "user_request": "Audit dependencies",
        "iteration": 1,
    }
    assert partial["project_id"] == "test-p1"
    assert partial.get("report_draft") is None
