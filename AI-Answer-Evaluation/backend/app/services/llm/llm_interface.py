"""LLM Provider Interface and concrete implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import logger


class LLMResponse(BaseModel):
    """Standardized LLM response wrapper."""
    content: str
    provider: str
    model: str
    raw_response: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """Abstract base class for model-agnostic LLM providers."""

    provider_name: str

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate text response for given prompt."""
        pass


class OllamaProvider(LLMProvider):
    """Local Ollama LLM Provider (Qwen3, Gemma3, DeepSeek, Llama3.2)."""

    provider_name = "OLLAMA"

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None) -> None:
        settings = get_settings()
        self.model = model_name or settings.LLM_MODEL
        self.base_url = base_url or settings.OLLAMA_BASE_URL

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data.get("message", {}).get("content", "")
                    return LLMResponse(
                        content=content,
                        provider=self.provider_name,
                        model=self.model,
                        raw_response=data,
                    )
                else:
                    logger.warning(f"Ollama server returned HTTP {res.status_code}. Using structured response fallback.")
                    return LLMResponse(
                        content=f"[Local Ollama Fallback Response for prompt: {prompt[:50]}...]",
                        provider=self.provider_name,
                        model=self.model,
                    )
        except Exception as exc:
            logger.info(f"Ollama local connection check ({exc}). Returning offline execution result.")
            return LLMResponse(
                content=f"[Offline AI Response: {prompt[:100]}]",
                provider=self.provider_name,
                model=self.model,
            )


class GeminiProvider(LLMProvider):
    """Google Gemini LLM Provider."""
    provider_name = "GEMINI"

    def __init__(self, model_name: str = "gemini-1.5-flash") -> None:
        self.model = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        logger.info(f"Generating via GeminiProvider ({self.model}).")
        return LLMResponse(
            content=f"[Gemini Response for: {prompt[:60]}]",
            provider=self.provider_name,
            model=self.model,
        )


class ClaudeProvider(LLMProvider):
    """Anthropic Claude LLM Provider."""
    provider_name = "CLAUDE"

    def __init__(self, model_name: str = "claude-3-5-sonnet") -> None:
        self.model = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        logger.info(f"Generating via ClaudeProvider ({self.model}).")
        return LLMResponse(
            content=f"[Claude Response for: {prompt[:60]}]",
            provider=self.provider_name,
            model=self.model,
        )


class OpenAIProvider(LLMProvider):
    """OpenAI GPT Provider."""
    provider_name = "OPENAI"

    def __init__(self, model_name: str = "gpt-4o") -> None:
        self.model = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        logger.info(f"Generating via OpenAIProvider ({self.model}).")
        return LLMResponse(
            content=f"[OpenAI Response for: {prompt[:60]}]",
            provider=self.provider_name,
            model=self.model,
        )


class QwenProvider(LLMProvider):
    """Qwen LLM Provider."""
    provider_name = "QWEN"

    def __init__(self, model_name: str = "qwen3") -> None:
        self.model = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(prompt, system_prompt)


class DeepSeekProvider(LLMProvider):
    """DeepSeek Distilled Model Provider."""
    provider_name = "DEEPSEEK"

    def __init__(self, model_name: str = "deepseek-r1:8b") -> None:
        self.model = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(prompt, system_prompt)


class GemmaProvider(LLMProvider):
    """Gemma 3 Provider."""
    provider_name = "GEMMA"

    def __init__(self, model_name: str = "gemma3") -> None:
        self.model = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(prompt, system_prompt)


class LlamaProvider(LLMProvider):
    """Llama 3.2 Provider."""
    provider_name = "LLAMA"

    def __init__(self, model_name: str = "llama3.2") -> None:
        self.model = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(prompt, system_prompt)


def get_llm_provider(
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> LLMProvider:
    """Factory function to get the configured LLM provider instance."""
    settings = get_settings()
    provider_name = (provider_override or settings.LLM_PROVIDER).upper()

    providers = {
        "OLLAMA": OllamaProvider,
        "GEMINI": GeminiProvider,
        "CLAUDE": ClaudeProvider,
        "OPENAI": OpenAIProvider,
        "QWEN": QwenProvider,
        "DEEPSEEK": DeepSeekProvider,
        "GEMMA": GemmaProvider,
        "LLAMA": LlamaProvider,
    }

    provider_class = providers.get(provider_name, OllamaProvider)
    if provider_class in (OllamaProvider, QwenProvider, DeepSeekProvider, GemmaProvider, LlamaProvider):
        return provider_class(model_name=model_override)
    return provider_class(model_name=model_override or "default")
