"""SecurityAgent for vulnerability patterns, auth, secrets, and input handling."""

from typing import Any

from backend.app.agents.base import BaseCodebaseAgent
from backend.app.agents.models import SecurityResult
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

SECURITY_SYSTEM_PROMPT = """You are an expert SecurityAgent.
Your job is to identify security patterns, authentication/authorization issues,
secrets exposure, unsafe input handling, dependency risks, and insecure API patterns.

CRITICAL INSTRUCTION: Do NOT claim a vulnerability without concrete, verifiable evidence.
If an issue is not directly proven by the code, classify it as 'info' or a recommendation.
Never invent or hallucinate vulnerabilities.

Return a valid JSON object matching the following schema:
{
  "agent_name": "SecurityAgent",
  "status": "completed",
  "summary": "Overall security assessment summary",
  "overall_posture": "e.g. Strong / Moderate / Vulnerable",
  "positive_security_controls": ["Control 1 (description)", "Control 2 (description)"],
  "findings": [
    {
      "title": "Finding title",
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "description": "Details with exact risk impact",
      "evidence": "Concrete snippet or citation from evidence",
      "file_path": "path/to/file.py",
      "start_line": 10,
      "end_line": 25,
      "recommendation": "Specific remediation step",
      "confidence": 0.85
    }
  ],
  "errors": [],
  "metadata": {}
}
"""


class SecurityAgent(BaseCodebaseAgent):
    """Agent responsible for identifying security vulnerabilities and verifying evidence."""

    agent_name: str = "SecurityAgent"

    async def analyze(
        self,
        project_id: str,
        user_request: str = "",
        context: dict[str, Any] | None = None,
    ) -> SecurityResult:
        """Analyze security posture and enforce evidence verification on all claims."""
        logger.info("Executing SecurityAgent for project %s", project_id)

        queries = [
            "authentication authorization password token secret jwt api_key",
            "sanitize validate sql injection exec subprocess eval",
            "cors permissions headers credentials encryption hash",
        ]

        chunks = await self.retrieve_evidence(project_id, queries, top_k=4)
        evidence_context = self.format_evidence_context(chunks)

        user_prompt = (
            f"Analyze the codebase security for project '{project_id}'.\n"
            f"User Objective: {user_request or 'General security audit'}\n\n"
            f"Codebase Evidence:\n{evidence_context}\n\n"
            "REMINDER: Do not claim any vulnerability without evidence. "
            "Produce the complete structured JSON analysis."
        )

        messages = [
            {"role": "system", "content": SECURITY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response_text = await self.llm_provider.generate_response(messages)
        result = self.parse_json_response(response_text, SecurityResult)
        result.agent_name = self.agent_name

        # Enforce contract: Downgrade any finding lacking direct code evidence
        for finding in result.findings:
            has_no_evidence = not finding.evidence or finding.evidence.strip() == ""
            has_no_file = not finding.file_path or finding.file_path.strip() == ""

            is_unsupported_claim = (has_no_evidence or has_no_file) and finding.severity in (
                "critical",
                "high",
                "medium",
            )
            if is_unsupported_claim:
                logger.warning(
                    "Downgrading unevidenced vulnerability claim '%s' from %s to info",
                    finding.title,
                    finding.severity,
                )
                finding.severity = "info"
                finding.description = f"[Unverified - missing code evidence] {finding.description}"

        return result
