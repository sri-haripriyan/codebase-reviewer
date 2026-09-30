"""Unit tests for LangGraph workflow routing, interruption, and checkpointing."""

import uuid

from langgraph.checkpoint.memory import MemorySaver

from backend.app.graph.edges import (
    ROUTE_FINALIZE,
    ROUTE_REVISE,
    route_human_review,
)
from backend.app.graph.state import create_initial_state
from backend.app.graph.workflow import create_analysis_workflow


def test_edge_routing_logic_direct():
    """Verify conditional edge routing decisions based on approval status and iteration."""
    # 1. Approved -> finalize
    state_approved = create_initial_state(project_id="p1")
    state_approved["approval_status"] = "approved"
    assert route_human_review(state_approved) == ROUTE_FINALIZE

    # 2. Feedback with iterations remaining -> revise
    state_feedback = create_initial_state(project_id="p1", max_iterations=3)
    state_feedback["approval_status"] = "feedback"
    state_feedback["iteration"] = 1
    assert route_human_review(state_feedback) == ROUTE_REVISE

    # 3. Feedback with max iterations reached -> finalize
    state_max_iter = create_initial_state(project_id="p1", max_iterations=3)
    state_max_iter["approval_status"] = "feedback"
    state_max_iter["iteration"] = 3
    assert route_human_review(state_max_iter) == ROUTE_FINALIZE

    # 4. Rejected with iterations remaining -> revise
    state_rejected = create_initial_state(project_id="p1", max_iterations=3)
    state_rejected["approval_status"] = "rejected"
    state_rejected["iteration"] = 2
    assert route_human_review(state_rejected) == ROUTE_REVISE

    # 5. Default fallback -> finalize
    state_pending = create_initial_state(project_id="p1")
    state_pending["approval_status"] = "pending"
    assert route_human_review(state_pending) == ROUTE_FINALIZE


def test_workflow_pause_at_human_review():
    """Verify workflow compiles with checkpointer and pauses execution before human_review."""
    memory = MemorySaver()
    workflow = create_analysis_workflow(checkpointer=memory)

    thread_id = f"thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    init_state = create_initial_state(project_id="proj-audit-1")

    # Initial invocation executes up to the interruption gate
    workflow.invoke(init_state, config)

    # State checkpoint inspection
    snapshot = workflow.get_state(config)
    assert snapshot.next == ("human_review",)
    assert snapshot.values["project_id"] == "proj-audit-1"
    assert snapshot.values["iteration"] == 1
    assert snapshot.values["report_draft"] is not None
    assert "executive_summary" in snapshot.values["report_draft"]
    assert snapshot.values["final_report"] is None


def test_workflow_resume_and_approval():
    """Verify resuming a paused workflow after approval terminates at END with final report."""
    memory = MemorySaver()
    workflow = create_analysis_workflow(checkpointer=memory)

    thread_id = f"thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    init_state = create_initial_state(project_id="proj-approve-1")

    # 1. Run until pause
    workflow.invoke(init_state, config)
    assert workflow.get_state(config).next == ("human_review",)

    # 2. Human reviewer approves the report draft
    workflow.update_state(config, {"approval_status": "approved"})

    # 3. Resume execution from checkpoint
    final_output = workflow.invoke(None, config)

    # 4. Verify workflow completion
    snapshot = workflow.get_state(config)
    assert snapshot.next == ()
    assert final_output["approval_status"] == "approved"
    assert final_output["final_report"] is not None
    assert final_output["final_report"] == final_output["report_draft"]


def test_workflow_feedback_revision_cycle():
    """Verify feedback loop: human feedback triggers revise node, reruns analysis, and pauses."""
    memory = MemorySaver()
    workflow = create_analysis_workflow(checkpointer=memory)

    thread_id = f"thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    init_state = create_initial_state(project_id="proj-feedback-1", max_iterations=3)

    # Turn 1: Initial run -> pauses at human_review (iteration 1)
    workflow.invoke(init_state, config)
    snap1 = workflow.get_state(config)
    assert snap1.next == ("human_review",)
    assert snap1.values["iteration"] == 1
    draft_v1 = snap1.values["report_draft"]
    assert draft_v1["iteration"] == 1

    # Human provides feedback requesting revision
    feedback_text = "Please examine SQL injection risks in repository models."
    workflow.update_state(
        config,
        {"approval_status": "feedback", "human_feedback": feedback_text},
    )

    # Turn 2: Resume -> executes revise -> prepare -> analysis -> report_gen -> pause
    workflow.invoke(None, config)
    snap2 = workflow.get_state(config)
    assert snap2.next == ("human_review",)
    assert snap2.values["iteration"] == 2
    draft_v2 = snap2.values["report_draft"]
    assert draft_v2["iteration"] == 2
    assert draft_v2["feedback_addressed"] == feedback_text

    # Human reviewer now approves the revised report
    workflow.update_state(config, {"approval_status": "approved"})
    final_output = workflow.invoke(None, config)

    assert workflow.get_state(config).next == ()
    assert final_output["final_report"]["iteration"] == 2
    assert final_output["approval_status"] == "approved"


def test_workflow_max_iterations_safety_guard():
    """Verify that repeated feedback cannot loop infinitely once max_iterations is reached."""
    memory = MemorySaver()
    workflow = create_analysis_workflow(checkpointer=memory)

    thread_id = f"thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    init_state = create_initial_state(project_id="proj-loop-1", max_iterations=2)

    # Turn 1 (iter 1) -> pause
    workflow.invoke(init_state, config)
    assert workflow.get_state(config).values["iteration"] == 1

    # Feedback 1 -> resume -> advance to iter 2 -> pause
    workflow.update_state(config, {"approval_status": "feedback", "human_feedback": "Iter 1 redo"})
    workflow.invoke(None, config)
    assert workflow.get_state(config).values["iteration"] == 2

    # Feedback 2 -> since iteration == max_iterations (2), route_human_review directs to finalize
    workflow.update_state(config, {"approval_status": "feedback", "human_feedback": "Iter 2 redo"})
    final_output = workflow.invoke(None, config)

    # Workflow terminates at finalize instead of looping indefinitely
    assert workflow.get_state(config).next == ()
    assert final_output["final_report"] is not None
    assert final_output["final_report"]["iteration"] == 2


def test_workflow_straight_through_execution():
    """Verify workflow executes end-to-end without interruption when interrupt_before is None."""
    workflow = create_analysis_workflow(checkpointer=MemorySaver(), interrupt_before=None)

    thread_id = f"thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    init_state = create_initial_state(project_id="proj-direct-1")
    init_state["approval_status"] = "approved"

    output = workflow.invoke(init_state, config)

    assert output["approval_status"] == "approved"
    assert output["final_report"] is not None
    assert workflow.get_state(config).next == ()


def test_root_graph_package_re_exports():
    """Verify root graph package re-exports state, nodes, edges, and workflow correctly."""
    from graph import (
        CodebaseAnalysisState,
        build_analysis_graph,
        create_analysis_workflow,
        create_initial_state,
        load_project_context,
        route_human_review,
    )

    assert CodebaseAnalysisState is not None
    assert callable(create_initial_state)
    assert callable(load_project_context)
    assert callable(route_human_review)
    assert callable(build_analysis_graph)
    assert callable(create_analysis_workflow)
