"""OpenAI and OpenAI-compatible API LLM provider."""

import httpx

from backend.app.core.config import settings
from backend.app.core.llm.base import BaseLLMProvider
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAILLMProvider(BaseLLMProvider):
    """LLM provider communicating with OpenAI or OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY or ""
        self.base_url = (
            base_url or settings.OPENAI_API_BASE or "https://api.openai.com/v1"
        ).rstrip("/")
        self.model_name = model_name or settings.LLM_MODEL_NAME

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
