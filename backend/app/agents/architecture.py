"""ArchitectureAgent for system architecture, components, data flows, and boundaries."""

from typing import Any

from backend.app.agents.base import BaseCodebaseAgent
from backend.app.agents.models import ArchitectureResult
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

ARCHITECTURE_SYSTEM_PROMPT = """You are an expert ArchitectureAgent.
Your job is to identify the architectural style, major components, dependencies, data flow,
API/service boundaries, and architectural concerns.

You MUST ground your analysis strictly in the provided codebase evidence.
Return a valid JSON object matching the following schema:
{
  "agent_name": "ArchitectureAgent",
  "status": "completed",
  "summary": "Summary of architectural patterns and components",
  "architectural_style": "e.g. Layered Service-Oriented Architecture",
  "major_components": ["Component1 (role)", "Component2 (role)"],
  "dependencies": ["FastAPI", "SQLAlchemy", "pgvector"],
  "data_flow": "Step-by-step description of data flow through the layers",
  "api_boundaries": ["/api/v1/health", "/projects"],
  "architectural_concerns": ["Observed risks or coupling issues"],
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
      "confidence": 0.90
    }
  ],
  "errors": [],
  "metadata": {}
}
"""


class ArchitectureAgent(BaseCodebaseAgent):
    """Agent responsible for identifying architecture patterns, component boundaries, and flows."""

    agent_name: str = "ArchitectureAgent"

    async def analyze(
        self,
        project_id: str,
        user_request: str = "",
        context: dict[str, Any] | None = None,
    ) -> ArchitectureResult:
        """Analyze architectural patterns, dependencies, data flow, and components."""
        logger.info("Executing ArchitectureAgent for project %s", project_id)

        queries = [
            "architecture service repository pattern database layer",
            "data flow schema model serializer router controller",
            "interface abstract client dependency injection boundaries",
        ]

        chunks = await self.retrieve_evidence(project_id, queries, top_k=4)
        evidence_context = self.format_evidence_context(chunks)

        user_prompt = (
            f"Analyze the system architecture for project '{project_id}'.\n"
            f"User Objective: {user_request or 'General architectural review'}\n\n"
            f"Codebase Evidence:\n{evidence_context}\n\n"
            "Produce the complete structured JSON analysis."
        )

        messages = [
            {"role": "system", "content": ARCHITECTURE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response_text = await self.llm_provider.generate_response(messages)
        result = self.parse_json_response(response_text, ArchitectureResult)
        result.agent_name = self.agent_name
        return result
