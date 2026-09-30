"""Mock LLM provider for deterministic unit and integration testing."""

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

        # Inspect the last user message for evidence context
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

        # Extract file paths and line ranges from evidence header
        # Pattern: File: <path> (Lines <start>-<end>)
        matches = re.findall(r"File:\s*([^\s\(\)]+)\s*\(Lines\s*(\d+)-(\d+)\)", last_user_msg)
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
