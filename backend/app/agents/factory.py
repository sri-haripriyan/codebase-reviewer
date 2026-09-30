"""Factory for instantiating specialized codebase analysis agents."""

from backend.app.agents.architecture import ArchitectureAgent
from backend.app.agents.base import BaseCodebaseAgent
from backend.app.agents.explorer import ExplorerAgent
from backend.app.agents.security import SecurityAgent
from backend.app.agents.testing_quality import TestingQualityAgent
from backend.app.core.llm.base import BaseLLMProvider
from backend.app.retrieval.service import RetrievalService


def get_analysis_agents(
    llm_provider: BaseLLMProvider | None = None,
    retrieval_service: RetrievalService | None = None,
) -> list[BaseCodebaseAgent]:
    """Instantiate and return the standard suite of specialized analysis agents."""
    return [
        ExplorerAgent(llm_provider=llm_provider, retrieval_service=retrieval_service),
        ArchitectureAgent(llm_provider=llm_provider, retrieval_service=retrieval_service),
        SecurityAgent(llm_provider=llm_provider, retrieval_service=retrieval_service),
        TestingQualityAgent(llm_provider=llm_provider, retrieval_service=retrieval_service),
    ]
