"""Unit tests for LangGraph placeholder workflow nodes."""

from backend.app.graph.nodes import (
    analysis,
    finalize,
    human_review,
    load_project_context,
    prepare_analysis,
    report_generation,
    revise,
)
from backend.app.graph.state import create_initial_state


def test_load_project_context_valid():
    """Verify load_project_context populates repository_summary."""
    state = create_initial_state(project_id="proj-valid-1")
    updates = load_project_context(state)

    assert "repository_summary" in updates
    assert updates["repository_summary"]["project_id"] == "proj-valid-1"
    assert updates["repository_summary"]["status"] == "ready"
    assert "detected_languages" in updates["repository_summary"]
    assert "errors" not in updates


def test_load_project_context_missing_project_id():
    """Verify load_project_context appends an error when project_id is empty."""
    state = create_initial_state(project_id="")
    updates = load_project_context(state)

    assert "errors" in updates
    assert len(updates["errors"]) == 1
    assert "Missing project_id" in updates["errors"][0]


def test_prepare_analysis():
    """Verify prepare_analysis generates placeholder retrieved evidence."""
    state = create_initial_state(project_id="proj-1")
    updates = prepare_analysis(state)

    assert "retrieved_evidence" in updates
    assert len(updates["retrieved_evidence"]) >= 1
    assert "file_path" in updates["retrieved_evidence"][0]
    assert "symbol" in updates["retrieved_evidence"][0]


def test_analysis_placeholder_agent_results():
    """Verify analysis executes specialized agents for all core domains."""
    state = create_initial_state(project_id="proj-1")
    updates = analysis(state)

    assert "agent_results" in updates
    results = updates["agent_results"]
    assert "explorer" in results
    assert "architecture" in results
    assert "security" in results
    assert "testing_quality" in results
    assert len(results["security"]["positive_security_controls"]) > 0


def test_report_generation():
    """Verify report_generation synthesizes draft and sets pending status."""
    state = create_initial_state(project_id="proj-1")
    state["agent_results"] = {"security": {"summary": "Secure"}}
    state["iteration"] = 1

    updates = report_generation(state)
    assert "report_draft" in updates
    assert updates["approval_status"] == "pending"

    draft = updates["report_draft"]
    assert draft["iteration"] == 1
    assert draft["project_id"] == "proj-1"
    assert "executive_summary" in draft


def test_human_review_node():
    """Verify human_review echoes current approval status and feedback."""
    state = create_initial_state(project_id="proj-1")
    state["approval_status"] = "feedback"
    state["human_feedback"] = "Add architecture diagram"

    updates = human_review(state)
    assert updates["approval_status"] == "feedback"
    assert updates["human_feedback"] == "Add architecture diagram"


def test_revise_node():
    """Verify revise advances iteration counter and resets approval status."""
    state = create_initial_state(project_id="proj-1")
    state["iteration"] = 1
    state["human_feedback"] = "Refactor database models"

    updates = revise(state)
    assert updates["iteration"] == 2
    assert updates["approval_status"] == "pending"


def test_finalize_node():
    """Verify finalize copies report_draft to final_report and marks approved."""
    state = create_initial_state(project_id="proj-1")
    draft = {"title": "Finalized Draft", "iteration": 2}
    state["report_draft"] = draft

    updates = finalize(state)
    assert updates["final_report"] == draft
    assert updates["approval_status"] == "approved"
