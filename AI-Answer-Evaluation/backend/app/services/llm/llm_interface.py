"""LLM Provider Interface and concrete implementations."""

from abc import ABC, abstractmethod
import time
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
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        """Generate text response for given prompt."""
        pass


class OllamaProvider(LLMProvider):
    """Local Ollama LLM Provider (Qwen3, Gemma3, DeepSeek, Llama3.2)."""

    provider_name = "OLLAMA"
    _is_live_cache: Optional[bool] = None
    _last_checked: float = 0.0

    @classmethod
    async def is_server_available(cls, base_url: str) -> bool:
        """Check if local Ollama server is alive with a 15-second cache."""
        now = time.time()
        if cls._is_live_cache is not None and (now - cls._last_checked) < 15.0:
            return cls._is_live_cache
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                res = await client.get(f"{base_url}/api/version")
                cls._is_live_cache = (res.status_code == 200)
        except Exception:
            cls._is_live_cache = False
        cls._last_checked = now
        return cls._is_live_cache

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None) -> None:
        settings = get_settings()
        self.model = model_name or settings.LLM_MODEL
        self.base_url = base_url or settings.OLLAMA_BASE_URL

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        settings = get_settings()
        is_live = await self.is_server_available(self.base_url)
        if not is_live:
            if strict:
                raise RuntimeError(f"Ollama local connection error: Server at {self.base_url} is unreachable.")
            logger.info("Ollama is offline (fast liveness check). Returning offline execution result.")
            return LLMResponse(
                content=f"[Offline AI Response: {prompt[:100]}]",
                provider=self.provider_name,
                model=self.model,
            )

        req_timeout = timeout or settings.REFINEMENT_TIMEOUT_SECONDS or 60.0


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
            async with httpx.AsyncClient(timeout=req_timeout) as client:
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
                    if strict:
                        raise RuntimeError(f"Ollama server returned HTTP {res.status_code}: {res.text}")
                    logger.warning(f"Ollama server returned HTTP {res.status_code}. Using structured response fallback.")
                    return LLMResponse(
                        content=f"[Local Ollama Fallback Response for prompt: {prompt[:50]}...]",
                        provider=self.provider_name,
                        model=self.model,
                    )
        except Exception as exc:
            if strict:
                raise RuntimeError(f"Ollama local connection error: {exc}") from exc
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

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        settings = get_settings()
        if not settings.ALLOW_CLOUD_LLM:
            raise PermissionError(
                "Cloud LLM provider 'GEMINI' is disabled (ALLOW_CLOUD_LLM=False). "
                "Enable cloud providers and authorize external processing."
            )
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Real Google Gemini API request via REST
        req_timeout = timeout or settings.REFINEMENT_TIMEOUT_SECONDS or 30.0
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={settings.GEMINI_API_KEY}"
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            res = await client.post(url, json={"contents": contents})
            if res.status_code != 200:
                raise RuntimeError(f"Gemini API returned HTTP {res.status_code}: {res.text}")
            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return LLMResponse(content=text, provider=self.provider_name, model=self.model, raw_response=data)


class ClaudeProvider(LLMProvider):
    """Anthropic Claude LLM Provider."""
    provider_name = "CLAUDE"

    def __init__(self, model_name: str = "claude-3-5-sonnet") -> None:
        self.model = model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        settings = get_settings()
        if not settings.ALLOW_CLOUD_LLM:
            raise PermissionError(
                "Cloud LLM provider 'CLAUDE' is disabled (ALLOW_CLOUD_LLM=False). "
                "Enable cloud providers and authorize external processing."
            )
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")

        req_timeout = timeout or settings.REFINEMENT_TIMEOUT_SECONDS or 30.0
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            body["system"] = system_prompt

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            res = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
            if res.status_code != 200:
                raise RuntimeError(f"Claude API returned HTTP {res.status_code}: {res.text}")
            data = res.json()
            text = data["content"][0]["text"]
            return LLMResponse(content=text, provider=self.provider_name, model=self.model, raw_response=data)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT Provider."""
    provider_name = "OPENAI"

    def __init__(self, model_name: str = "gpt-4o") -> None:
        self.model = model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        settings = get_settings()
        if not settings.ALLOW_CLOUD_LLM:
            raise PermissionError(
                "Cloud LLM provider 'OPENAI' is disabled (ALLOW_CLOUD_LLM=False). "
                "Enable cloud providers and authorize external processing."
            )
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured.")

        req_timeout = timeout or settings.REFINEMENT_TIMEOUT_SECONDS or 30.0
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json={"model": self.model, "messages": messages})
            if res.status_code != 200:
                raise RuntimeError(f"OpenAI API returned HTTP {res.status_code}: {res.text}")
            data = res.json()
            text = data["choices"][0]["message"]["content"]
            return LLMResponse(content=text, provider=self.provider_name, model=self.model, raw_response=data)


class QwenProvider(LLMProvider):
    """Qwen LLM Provider."""
    provider_name = "QWEN"

    def __init__(self, model_name: str = "qwen3") -> None:
        self.model = model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(
            prompt, system_prompt=system_prompt, timeout=timeout, strict=strict
        )


class DeepSeekProvider(LLMProvider):
    """DeepSeek Distilled Model Provider."""
    provider_name = "DEEPSEEK"

    def __init__(self, model_name: str = "deepseek-r1:8b") -> None:
        self.model = model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(
            prompt, system_prompt=system_prompt, timeout=timeout, strict=strict
        )


class GemmaProvider(LLMProvider):
    """Gemma 3 Provider."""
    provider_name = "GEMMA"

    def __init__(self, model_name: str = "gemma3") -> None:
        self.model = model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(
            prompt, system_prompt=system_prompt, timeout=timeout, strict=strict
        )


class LlamaProvider(LLMProvider):
    """Llama 3.2 Provider."""
    provider_name = "LLAMA"

    def __init__(self, model_name: str = "llama3.2") -> None:
        self.model = model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        strict: bool = False,
    ) -> LLMResponse:
        return await OllamaProvider(model_name=self.model).generate(
            prompt, system_prompt=system_prompt, timeout=timeout, strict=strict
        )


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
