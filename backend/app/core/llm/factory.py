"""Factory for resolving and instantiating LLM providers."""

from backend.app.core.config import settings
from backend.app.core.llm.base import BaseLLMProvider
from backend.app.core.llm.mock_provider import MockLLMProvider
from backend.app.core.llm.openai_provider import OpenAILLMProvider
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

_GLOBAL_LLM: BaseLLMProvider | None = None


def get_llm_provider(
    provider_type: str | None = None,
    force_new: bool = False,
) -> BaseLLMProvider:
    """Return an LLM provider based on provider_type or application settings."""
    global _GLOBAL_LLM

    if not force_new and _GLOBAL_LLM is not None and provider_type is None:
        return _GLOBAL_LLM

    chosen = (provider_type or settings.LLM_PROVIDER).strip().lower()

    if chosen == "openai":
        provider = OpenAILLMProvider()
    elif chosen == "mock":
        provider = MockLLMProvider()
    elif chosen == "ollama":
        provider = OpenAILLMProvider(
            base_url=settings.OPENAI_API_BASE or "http://localhost:11434/v1",
            api_key="ollama",
        )
    else:
        logger.warning("Unknown LLM provider '%s'. Defaulting to Mock provider.", chosen)
        provider = MockLLMProvider()

    if provider_type is None and not force_new:
        _GLOBAL_LLM = provider

    return provider
