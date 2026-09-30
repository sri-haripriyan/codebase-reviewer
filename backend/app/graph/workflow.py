"""Workflow builder and graph orchestration for codebase analysis."""

from collections.abc import Sequence

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.graph.edges import (
    HUMAN_REVIEW_CONDITIONAL_TARGETS,
    route_human_review,
)
from backend.app.graph.nodes import (
    analysis,
    finalize,
    human_review,
    load_project_context,
    prepare_analysis,
    report_generation,
    revise,
)
from backend.app.graph.state import CodebaseAnalysisState


def build_analysis_graph() -> StateGraph:
    """Construct the uncompiled StateGraph for codebase analysis.

    Flow topology:
    START
      ↓
    load_project_context
      ↓
    prepare_analysis  <────────────┐
      ↓                            │
    analysis                       │
      ↓                            │
    report_generation              │
      ↓                            │
    human_review                   │
      ↓ (conditional routing)      │
      ├── approved → finalize ─> END
      └── feedback → revise ───────┘
    """
    builder = StateGraph(CodebaseAnalysisState)

    # 1. Register nodes
    builder.add_node("load_project_context", load_project_context)
    builder.add_node("prepare_analysis", prepare_analysis)
    builder.add_node("analysis", analysis)
    builder.add_node("report_generation", report_generation)
    builder.add_node("human_review", human_review)
    builder.add_node("finalize", finalize)
    builder.add_node("revise", revise)

    # 2. Linear pipeline edges
    builder.add_edge(START, "load_project_context")
    builder.add_edge("load_project_context", "prepare_analysis")
    builder.add_edge("prepare_analysis", "analysis")
    builder.add_edge("analysis", "report_generation")
    builder.add_edge("report_generation", "human_review")

    # 3. Conditional routing from human_review gate
    builder.add_conditional_edges(
        "human_review",
        route_human_review,
        HUMAN_REVIEW_CONDITIONAL_TARGETS,
    )

    # 4. Terminal and feedback cycle edges
    builder.add_edge("finalize", END)
    builder.add_edge("revise", "prepare_analysis")

    return builder


def create_analysis_workflow(
    checkpointer: BaseCheckpointSaver | None = None,
    interrupt_before: Sequence[str] | None = ("human_review",),
) -> CompiledStateGraph:
    """Build and compile the codebase analysis workflow with state checkpointing.

    Args:
        checkpointer: State persistence checkpointer. Defaults to in-memory MemorySaver.
        interrupt_before: Nodes before which to interrupt workflow execution.
            Defaults to ('human_review',) for human-in-the-loop review.

    Returns:
        CompiledStateGraph ready for execution, pausing, and resumption.
    """
    builder = build_analysis_graph()
    active_checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    active_interrupt_before = list(interrupt_before) if interrupt_before is not None else []

    return builder.compile(
        checkpointer=active_checkpointer,
        interrupt_before=active_interrupt_before,
    )


# Module-level default workflow instance with MemorySaver checkpointer
_default_workflow: CompiledStateGraph | None = None


def get_analysis_workflow(reset: bool = False) -> CompiledStateGraph:
    """Retrieve or initialize the default compiled codebase analysis workflow."""
    global _default_workflow
    if _default_workflow is None or reset:
        _default_workflow = create_analysis_workflow()
    return _default_workflow
