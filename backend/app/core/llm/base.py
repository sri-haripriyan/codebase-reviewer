"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Abstract interface for large language model generation providers."""

    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> str:
        """Generate a chat completion response from a list of messages."""
        pass
