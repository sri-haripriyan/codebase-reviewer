"""Base abstraction for specialized codebase analysis agents."""

import json
import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from backend.app.agents.models import BaseAgentResult
from backend.app.core.llm.base import BaseLLMProvider
from backend.app.core.llm.factory import get_llm_provider
from backend.app.core.logging import get_logger
from backend.app.retrieval.models import EvidenceChunk, SearchQuery
from backend.app.retrieval.service import RetrievalService

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseAgentResult)


class BaseCodebaseAgent(ABC):
    """Abstract base class for domain-specialized codebase analysis agents."""

    agent_name: str = "BaseAgent"

    def __init__(
        self,
        llm_provider: BaseLLMProvider | None = None,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self.llm_provider = llm_provider or get_llm_provider()
        self.retrieval_service = retrieval_service

    @abstractmethod
    async def analyze(
        self,
        project_id: str,
        user_request: str = "",
        context: dict[str, Any] | None = None,
    ) -> BaseAgentResult:
        """Execute domain analysis grounded in retrieved codebase evidence."""

    async def retrieve_evidence(
        self,
        project_id: str,
        queries: list[str],
        top_k: int = 4,
    ) -> list[EvidenceChunk]:
        """Fetch code evidence using the RetrievalService across targeted domain queries."""
        if not self.retrieval_service:
            return []

        collected_chunks: list[EvidenceChunk] = []
        seen_chunk_ids: set[str] = set()

        try:
            pid = uuid.UUID(project_id)
        except (ValueError, TypeError):
            logger.warning("Invalid project_id UUID format: %s", project_id)
            return []

        for q_text in queries:
            try:
                search_query = SearchQuery(
                    query=q_text,
                    project_id=pid,
                    top_k=top_k,
                    search_type="hybrid",
                )
                result = await self.retrieval_service.search(search_query)
                chunks = getattr(result, "evidence", getattr(result, "chunks", []))
                for chunk in chunks:
                    if chunk.chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk.chunk_id)
                        collected_chunks.append(chunk)
            except Exception as e:
                logger.warning(
                    "Retrieval query '%s' failed in %s: %s",
                    q_text,
                    self.agent_name,
                    e,
                )

        return collected_chunks

    def format_evidence_context(self, chunks: list[EvidenceChunk]) -> str:
        """Format retrieved code chunks into a compact, grounded context block."""
        if not chunks:
            return "No specific code chunks retrieved for this analysis."

        blocks = []
        for c in chunks:
            symbol_info = f" | Symbol: `{c.symbol}`" if c.symbol else ""
            header = f"[File: {c.file_path} (Lines {c.start_line}-{c.end_line}){symbol_info}]"
            content = c.chunk_content.strip()
            blocks.append(f"{header}\n```\n{content}\n```")

        return "\n\n".join(blocks)

    def parse_json_response(self, text: str, model_cls: type[T]) -> T:
        """Clean markdown wrapping and parse LLM response into target Pydantic model."""
        cleaned = text.strip()
        # Remove markdown code fence if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            return model_cls.model_validate(data)
        except Exception as e:
            logger.warning(
                "JSON parse error in %s: %s. Attempting regex extraction.",
                self.agent_name,
                e,
            )
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return model_cls.model_validate(data)
                except Exception:
                    pass

            # Fallback to default instance on parse failure
            return model_cls(
                agent_name=self.agent_name,
                status="partial",
                summary=f"Analysis completed with unparsed output: {text[:150]}...",
                errors=[f"Failed to parse structured JSON: {e}"],
            )
