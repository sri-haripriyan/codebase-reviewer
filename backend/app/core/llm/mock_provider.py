"""Mock LLM provider for deterministic unit and integration testing."""

import json
import re

from backend.app.core.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing without external API calls."""

    def __init__(self, fixed_response: str | None = None) -> None:
        self.fixed_response = fixed_response
        self.recorded_calls: list[list[dict[str, str]]] = []
        self.call_count = 0

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> str:
        self.call_count += 1
        self.recorded_calls.append(messages)

        if self.fixed_response is not None:
            return self.fixed_response

        # Check full prompt text for agent type indicators
        combined_text = " ".join(m.get("content", "") for m in messages)

        # 1. Specialized Agent Mock Responses
        if "ExplorerAgent" in combined_text or "explorer agent" in combined_text.lower():
            return json.dumps(
                {
                    "agent_name": "ExplorerAgent",
                    "status": "completed",
                    "summary": "Repository overview: Modular FastAPI backend with LangGraph.",
                    "overview": "Production-oriented AI codebase reviewer system.",
                    "major_modules": [
                        "api",
                        "chat",
                        "chunker",
                        "core",
                        "graph",
                        "models",
                        "retrieval",
                    ],
                    "entry_points": ["backend/app/main.py"],
                    "configuration_files": ["backend/app/core/config.py", "pyproject.toml"],
                    "important_files": ["backend/app/main.py", "backend/app/graph/workflow.py"],
                    "findings": [
                        {
                            "title": "Clean modular directory structure",
                            "severity": "info",
                            "description": "Standard separation of concerns across modules.",
                            "evidence": "[backend/app/main.py:1-30]",
                            "file_path": "backend/app/main.py",
                            "start_line": 1,
                            "end_line": 30,
                            "recommendation": "Preserve module boundaries as codebase grows.",
                            "confidence": 0.95,
                        }
                    ],
                    "errors": [],
                    "metadata": {"files_scanned": 42},
                }
            )

        if "ArchitectureAgent" in combined_text or "architecture agent" in combined_text.lower():
            return json.dumps(
                {
                    "agent_name": "ArchitectureAgent",
                    "status": "completed",
                    "summary": "Layered service-oriented architecture with repository pattern.",
                    "architectural_style": "Layered Service-Oriented Architecture",
                    "major_components": [
                        "FastAPI Endpoints",
                        "Chat Service",
                        "Repositories",
                        "LangGraph Workflow",
                    ],
                    "dependencies": ["FastAPI", "SQLAlchemy", "pgvector", "LangGraph", "Pydantic"],
                    "data_flow": "HTTP Request -> Router -> Service -> Repository -> PostgreSQL",
                    "api_boundaries": ["/api/v1/health", "/projects", "/projects/{id}/chat"],
                    "architectural_concerns": ["Asynchronous connection lifecycle during tests"],
                    "findings": [
                        {
                            "title": "Strict repository pattern isolation",
                            "severity": "info",
                            "description": "Repositories encapsulate database operations cleanly.",
                            "evidence": "[backend/app/repositories/project_repository.py:1-40]",
                            "file_path": "backend/app/repositories/project_repository.py",
                            "start_line": 1,
                            "end_line": 40,
                            "recommendation": "Maintain project-scoped queries across all queries.",
                            "confidence": 0.92,
                        }
                    ],
                    "errors": [],
                    "metadata": {},
                }
            )

        if "SecurityAgent" in combined_text or "security agent" in combined_text.lower():
            return json.dumps(
                {
                    "agent_name": "SecurityAgent",
                    "status": "completed",
                    "summary": "Overall security posture is solid. Parameterized queries and auth.",
                    "overall_posture": "Solid",
                    "positive_security_controls": [
                        "SQLAlchemy ORM parameterized statements prevent SQL injection",
                        "ZipSlip directory traversal protection in archive extraction",
                        "Project-scoped SQL filtering preventing cross-tenant data leakage",
                    ],
                    "findings": [
                        {
                            "title": "CORS configuration permits development origins",
                            "severity": "low",
                            "description": "Default configuration permits local origins.",
                            "evidence": "[backend/app/core/config.py:30-45]",
                            "file_path": "backend/app/core/config.py",
                            "start_line": 30,
                            "end_line": 45,
                            "recommendation": "Verify CORS_ORIGINS in production deployment.",
                            "confidence": 0.88,
                        }
                    ],
                    "errors": [],
                    "metadata": {"positive_controls_count": 3},
                }
            )

        if "TestingQualityAgent" in combined_text or "testing agent" in combined_text.lower():
            return json.dumps(
                {
                    "agent_name": "TestingQualityAgent",
                    "status": "completed",
                    "summary": "Extensive unit and integration test coverage with pytest.",
                    "test_frameworks": ["pytest", "pytest-asyncio"],
                    "test_coverage_indicators": "Comprehensive unit tests across models and graph.",
                    "missing_test_areas": ["End-to-end performance benchmarking under heavy load"],
                    "code_smells_and_maintainability": ["Clean typing with Pydantic throughout"],
                    "findings": [
                        {
                            "title": "Robust async fixture isolation",
                            "severity": "info",
                            "description": "Database fixtures roll back changes cleanly.",
                            "evidence": "[tests/conftest.py:25-39]",
                            "file_path": "tests/conftest.py",
                            "start_line": 25,
                            "end_line": 39,
                            "recommendation": "Add automated regression tests as dataset grows.",
                            "confidence": 0.90,
                        }
                    ],
                    "errors": [],
                    "metadata": {"test_suites_detected": ["unit", "integration"]},
                }
            )

        # 2. Conversational Q&A Mock Logic (Module 06)
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )

        insufficient_msg = (
            "The provided codebase evidence does not contain sufficient information "
            "to answer this question."
        )

        has_no_snippets = "No relevant code snippets were found" in last_user_msg
        if has_no_snippets or "--- CODE EVIDENCE ---" not in last_user_msg:
            return insufficient_msg

        matches = re.findall(
            r"File:\s*([^\s\(\)]+)\s*\(Lines\s*(\d+)-(\d+)\)",
            last_user_msg,
        )
        symbol_matches = re.findall(r"Symbol:\s*([^\s\(\)]+)", last_user_msg)

        if not matches:
            return insufficient_msg

        citations = [f"[{m[0]}:{m[1]}-{m[2]}]" for m in matches]
        symbols_str = (
            ", ".join(f"`{s}`" for s in symbol_matches) if symbol_matches else "the relevant logic"
        )

        citation_str = " ".join(citations)
        return (
            f"Based on the provided codebase evidence, {symbols_str} "
            f"is implemented at {citation_str}."
        )
