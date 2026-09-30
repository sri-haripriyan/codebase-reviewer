"""ExplorerAgent for repository structure, modules, entrypoints, and configurations."""

from typing import Any

from backend.app.agents.base import BaseCodebaseAgent
from backend.app.agents.models import ExplorerResult
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

EXPLORER_SYSTEM_PROMPT = """You are an expert ExplorerAgent.
Your job is to understand repository structure, major modules, entry points,
configuration, and key files.

You MUST ground your analysis strictly in the provided codebase evidence.
Return a valid JSON object matching the following schema:
{
  "agent_name": "ExplorerAgent",
  "status": "completed",
  "summary": "High-level summary of codebase layout and composition",
  "overview": "Comprehensive overview of the repository",
  "major_modules": ["module1 (description)", "module2 (description)"],
  "entry_points": ["path/to/entry.py"],
  "configuration_files": ["path/to/config.py"],
  "important_files": ["path/to/important.py"],
  "findings": [
    {
      "title": "Finding title",
      "severity": "info",
      "description": "Details",
      "evidence": "Evidence citation or snippet",
      "file_path": "path/to/file.py",
      "start_line": 1,
      "end_line": 20,
      "recommendation": "Recommendation",
      "confidence": 0.95
    }
  ],
  "errors": [],
  "metadata": {}
}
"""


class ExplorerAgent(BaseCodebaseAgent):
    """Agent responsible for codebase discovery, structure, modules, and entrypoints."""

    agent_name: str = "ExplorerAgent"

    async def analyze(
        self,
        project_id: str,
        user_request: str = "",
        context: dict[str, Any] | None = None,
    ) -> ExplorerResult:
        """Discover modules, entrypoints, configuration files, and repo layout."""
        logger.info("Executing ExplorerAgent for project %s", project_id)

        queries = [
            "main app entrypoint bootstrap startup",
            "configuration settings config environment pyproject",
            "router api endpoints routes controller",
        ]

        chunks = await self.retrieve_evidence(project_id, queries, top_k=4)
        evidence_context = self.format_evidence_context(chunks)

        user_prompt = (
            f"Analyze the codebase structure for project '{project_id}'.\n"
            f"User Objective: {user_request or 'General codebase exploration'}\n\n"
            f"Codebase Evidence:\n{evidence_context}\n\n"
            "Produce the complete structured JSON analysis."
        )

        messages = [
            {"role": "system", "content": EXPLORER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response_text = await self.llm_provider.generate_response(messages)
        result = self.parse_json_response(response_text, ExplorerResult)
        result.agent_name = self.agent_name
        return result
