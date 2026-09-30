"""Unit tests for LangGraph orchestrator concurrent agent execution and resilience."""

from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver

from backend.app.agents.security import SecurityAgent
from backend.app.graph.nodes import analysis
from backend.app.graph.state import create_initial_state
from backend.app.graph.workflow import create_analysis_workflow


def test_concurrent_agent_execution_and_results():
    """Verify analysis node executes all 4 domain agents and collects structured results."""
    state = create_initial_state(project_id="proj-orch-1")

    updates = analysis(state)

    assert "agent_results" in updates
    results = updates["agent_results"]

    # All 4 agent domains must be represented
    assert "explorer" in results
    assert "architecture" in results
    assert "security" in results
    assert "testing_quality" in results

    # Verify structured content in results
    assert results["explorer"]["agent_name"] == "ExplorerAgent"
    assert results["architecture"]["agent_name"] == "ArchitectureAgent"
    assert results["security"]["agent_name"] == "SecurityAgent"
    assert results["testing_quality"]["agent_name"] == "TestingQualityAgent"

    # Verify evidence preservation
    assert "retrieved_evidence" in updates
    assert len(updates["retrieved_evidence"]) > 0


def test_agent_failure_resilience():
    """Verify orchestrator handles an individual agent failure without halting workflow."""
    state = create_initial_state(project_id="proj-fail-resilience")

    # Simulate SecurityAgent encountering an unhandled network/API exception
    with patch.object(
        SecurityAgent,
        "analyze",
        side_effect=RuntimeError("Security LLM API timeout"),
    ):
        updates = analysis(state)

    # Workflow must not crash; errors must capture the failure
    assert "errors" in updates
    assert any("Security LLM API timeout" in err for err in updates["errors"])

    # Security domain marked failed with error details
    results = updates["agent_results"]
    assert results["security"]["status"] == "failed"
    assert "Security LLM API timeout" in results["security"]["errors"][0]

    # The other 3 agents must still succeed completely
    assert results["explorer"]["status"] == "completed"
    assert results["architecture"]["status"] == "completed"
    assert results["testing_quality"]["status"] == "completed"


def test_full_workflow_with_agent_report_draft():
    """Verify entire LangGraph workflow produces agent-grounded report draft at review gate."""
    memory = MemorySaver()
    workflow = create_analysis_workflow(checkpointer=memory)

    config = {"configurable": {"thread_id": "thread-orch-e2e"}}
    init_state = create_initial_state(project_id="proj-full-e2e")

    # 1. Run workflow -> pauses at human_review
    workflow.invoke(init_state, config)

    snap = workflow.get_state(config)
    assert snap.next == ("human_review",)

    # Check that report_draft contains sections populated by the specialized agents
    draft = snap.values["report_draft"]
    assert draft is not None
    assert "sections" in draft
    sections = draft["sections"]
    assert "architecture" in sections
    assert "security" in sections
    assert "explorer" in sections
    assert "testing_quality" in sections

    # 2. Reviewer approves -> workflow completes
    workflow.update_state(config, {"approval_status": "approved"})
    final_output = workflow.invoke(None, config)

    assert workflow.get_state(config).next == ()
    assert final_output["approval_status"] == "approved"
    assert final_output["final_report"]["sections"] == sections
