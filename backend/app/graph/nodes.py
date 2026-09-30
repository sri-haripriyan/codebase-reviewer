"""Nodes for LangGraph codebase analysis workflow integrating specialized agents."""

import asyncio
import concurrent.futures
from typing import Any

from backend.app.agents.factory import get_analysis_agents
from backend.app.core.logging import get_logger
from backend.app.graph.state import CodebaseAnalysisState

logger = get_logger(__name__)


def load_project_context(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Load project metadata, structure, and initialization parameters."""
    project_id = state.get("project_id", "")
    if not project_id:
        return {
            "errors": ["Missing project_id in analysis state."],
            "iteration": state.get("iteration", 1),
        }

    logger.info("Loading project context for project_id: %s", project_id)

    repo_summary = {
        "project_id": project_id,
        "status": "ready",
        "detected_languages": ["python", "typescript"],
        "total_files": 42,
        "source_type": "github",
    }

    return {
        "repository_summary": repo_summary,
        "iteration": state.get("iteration", 1),
        "max_iterations": state.get("max_iterations", 3),
    }


def prepare_analysis(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Plan analysis tasks, incorporate any human feedback, and collect evidence."""
    iteration = state.get("iteration", 1)
    feedback = state.get("human_feedback")
    logger.info("Preparing analysis plan (iteration %d, feedback: %s)", iteration, feedback)

    evidence = [
        {
            "file_path": "src/core/main.py",
            "symbol": "AppBootstrap",
            "summary": "Core application entry point and lifecycle management.",
        },
        {
            "file_path": "src/security/auth.py",
            "symbol": "verify_token",
            "summary": "JWT authentication verification handler.",
        },
    ]

    return {"retrieved_evidence": evidence}


AGENT_DOMAIN_MAP = {
    "ExplorerAgent": "explorer",
    "ArchitectureAgent": "architecture",
    "SecurityAgent": "security",
    "TestingQualityAgent": "testing_quality",
}


async def async_analysis(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Execute specialized analysis agents concurrently with fault tolerance."""
    project_id = state.get("project_id", "")
    user_request = state.get("user_request", "")
    iteration = state.get("iteration", 1)

    logger.info(
        "Executing concurrent analysis agents for project %s (iter %d)",
        project_id,
        iteration,
    )

    agents = get_analysis_agents()
    context = {
        "repository_summary": state.get("repository_summary", {}),
        "iteration": iteration,
        "human_feedback": state.get("human_feedback"),
        "retrieved_evidence": state.get("retrieved_evidence", []),
    }

    # Execute all independent domain agents concurrently
    tasks = [agent.analyze(project_id, user_request, context) for agent in agents]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    agent_results: dict[str, Any] = dict(state.get("agent_results") or {})
    accumulated_evidence: list[dict[str, Any]] = list(state.get("retrieved_evidence") or [])
    errors: list[str] = []

    for agent, result in zip(agents, raw_results):
        domain_key = AGENT_DOMAIN_MAP.get(
            agent.agent_name, agent.agent_name.lower().replace("agent", "")
        )
        if isinstance(result, Exception):
            error_msg = f"Agent '{agent.agent_name}' failed: {result}"
            logger.error(error_msg)
            errors.append(error_msg)
            agent_results[domain_key] = {
                "agent_name": agent.agent_name,
                "status": "failed",
                "summary": f"Analysis failed: {result}",
                "findings": [],
                "errors": [str(result)],
            }
        else:
            agent_results[domain_key] = result.model_dump()
            if domain_key == "testing_quality":
                agent_results["code_quality"] = agent_results["testing_quality"]

            # Preserve evidence discovered by agent findings
            for finding in result.findings:
                if finding.file_path and finding.evidence:
                    accumulated_evidence.append(
                        {
                            "file_path": finding.file_path,
                            "symbol": finding.title,
                            "start_line": finding.start_line,
                            "end_line": finding.end_line,
                            "content": finding.evidence,
                        }
                    )

    updates: dict[str, Any] = {
        "agent_results": agent_results,
        "retrieved_evidence": accumulated_evidence,
    }
    if errors:
        updates["errors"] = errors
    return updates


def analysis(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Execute analysis agents concurrently, supporting sync and async callers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, async_analysis(state)).result()
    else:
        return asyncio.run(async_analysis(state))


def report_generation(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Synthesize analysis results and evidence into a structured report draft."""
    iteration = state.get("iteration", 1)
    project_id = state.get("project_id", "unknown")
    logger.info("Generating report draft v%d for project %s", iteration, project_id)

    report_draft = {
        "title": f"Codebase Analysis Report (v{iteration})",
        "project_id": project_id,
        "iteration": iteration,
        "executive_summary": (
            f"Analysis performed for request: '{state.get('user_request')}'. "
            "Specialized agents evaluated architecture, security, quality, and structure."
        ),
        "sections": state.get("agent_results", {}),
        "evidence_count": len(state.get("retrieved_evidence", [])),
        "feedback_addressed": state.get("human_feedback"),
    }

    return {
        "report_draft": report_draft,
        "approval_status": "pending",
    }


def human_review(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Human review gate validating approval status or capturing feedback."""
    approval = state.get("approval_status", "pending")
    feedback = state.get("human_feedback")

    logger.info(
        "Processing human review node (status=%s, feedback=%s)",
        approval,
        feedback,
    )

    return {
        "approval_status": approval,
        "human_feedback": feedback,
    }


def revise(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Increment iteration and prepare state for revision based on human feedback."""
    current_iter = state.get("iteration", 1)
    next_iter = current_iter + 1
    feedback = state.get("human_feedback")

    logger.info(
        "Executing revision loop: advancing iteration from %d to %d (feedback: %s)",
        current_iter,
        next_iter,
        feedback,
    )

    return {
        "iteration": next_iter,
        "approval_status": "pending",
    }


def finalize(state: CodebaseAnalysisState) -> dict[str, Any]:
    """Finalize the approved report draft as the final report."""
    logger.info(
        "Finalizing analysis report for project %s at iteration %d",
        state.get("project_id"),
        state.get("iteration", 1),
    )

    return {
        "final_report": state.get("report_draft"),
        "approval_status": "approved",
    }
