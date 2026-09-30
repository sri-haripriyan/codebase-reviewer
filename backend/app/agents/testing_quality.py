"""TestingQualityAgent for test frameworks, coverage, error handling, and maintainability."""

from typing import Any

from backend.app.agents.base import BaseCodebaseAgent
from backend.app.agents.models import TestingQualityResult
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

TESTING_QUALITY_SYSTEM_PROMPT = """You are an expert TestingQualityAgent.
Your job is to identify test frameworks, test coverage indicators, missing tests,
error handling, maintainability, code smells, and reliability concerns.

You MUST ground your analysis strictly in the provided codebase evidence.
Return a valid JSON object matching the following schema:
{
  "agent_name": "TestingQualityAgent",
  "status": "completed",
  "summary": "Assessment of testing practices, code quality, and maintainability",
  "test_frameworks": ["pytest", "unittest"],
  "test_coverage_indicators": "Observations regarding test depth and fixture organization",
  "missing_test_areas": ["Untested modules or integration gaps"],
  "code_smells_and_maintainability": ["Identified smells or maintainability hurdles"],
  "findings": [
    {
      "title": "Finding title",
      "severity": "info" | "low" | "medium" | "high",
      "description": "Details",
      "evidence": "Evidence citation or snippet",
      "file_path": "path/to/file.py",
      "start_line": 1,
      "end_line": 20,
      "recommendation": "Recommendation",
      "confidence": 0.88
    }
  ],
  "errors": [],
  "metadata": {}
}
"""


class TestingQualityAgent(BaseCodebaseAgent):
    """Agent responsible for auditing test suites, code quality, error handling, and smells."""

    __test__ = False
    agent_name: str = "TestingQualityAgent"

    async def analyze(
        self,
        project_id: str,
        user_request: str = "",
        context: dict[str, Any] | None = None,
    ) -> TestingQualityResult:
        """Analyze test framework coverage, error resilience, and code quality."""
        logger.info("Executing TestingQualityAgent for project %s", project_id)

        queries = [
            "test assert pytest fixture mock unittest test_",
            "exception error handler try catch raise logger",
            "validate schema verify check maintainability reliability",
        ]

        chunks = await self.retrieve_evidence(project_id, queries, top_k=4)
        evidence_context = self.format_evidence_context(chunks)

        user_prompt = (
            f"Analyze test coverage and code quality for project '{project_id}'.\n"
            f"User Objective: {user_request or 'General quality audit'}\n\n"
            f"Codebase Evidence:\n{evidence_context}\n\n"
            "Produce the complete structured JSON analysis."
        )

        messages = [
            {"role": "system", "content": TESTING_QUALITY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response_text = await self.llm_provider.generate_response(messages)
        result = self.parse_json_response(response_text, TestingQualityResult)
        result.agent_name = self.agent_name
        return result
