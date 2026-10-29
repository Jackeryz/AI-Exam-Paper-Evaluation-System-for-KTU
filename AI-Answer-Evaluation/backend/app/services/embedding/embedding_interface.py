"""Embedding Provider interface and concrete implementations."""

from abc import ABC, abstractmethod
import re
from typing import List, Optional
import numpy as np

from app.core.config import get_settings
from app.core.logging import logger


class EmbeddingProvider(ABC):
    """Abstract base class for text embedding generation providers."""

    provider_name: str

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding vector for a single query text."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of document strings."""
        pass


class BGEProvider(EmbeddingProvider):
    """BAAI/bge-small-en-v1.5 local embedding provider implementation."""

    provider_name = "BGE"

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                import os
                os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except BaseException as exc:
                logger.info(f"SentenceTransformer not loaded ({exc}). Using normalized hash vector generator.")
                self._model = "fallback"
        return self._model

    def _hash_vector(self, text: str, dim: int = 384) -> List[float]:
        """Deterministic feature-hashed bag-of-words vector calculation for offline execution."""
        words = [w for w in re.findall(r"\w+", text.lower()) if len(w) > 1]
        if not words:
            return [0.0] * dim
        vec = np.zeros(dim, dtype=float)
        for w in words:
            idx = abs(hash(w)) % dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return (vec / (norm if norm > 0.0 else 1.0)).tolist()

    def embed_query(self, text: str) -> List[float]:
        model = self._get_model()
        if model == "fallback":
            return self._hash_vector(text)
        return model.encode(text, convert_to_numpy=True).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        if model == "fallback":
            return [self._hash_vector(t) for t in texts]
        return model.encode(texts, convert_to_numpy=True).tolist()


class E5Provider(EmbeddingProvider):
    """Multilingual / English E5 embedding provider."""
    provider_name = "E5"

    def __init__(self, model_name: str = "intfloat/e5-small-v2") -> None:
        self.model_name = model_name

    def embed_query(self, text: str) -> List[float]:
        return BGEProvider(self.model_name).embed_query(f"query: {text}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return BGEProvider(self.model_name).embed_documents([f"passage: {t}" for t in texts])


class JinaProvider(EmbeddingProvider):
    """Jina Embeddings v2 provider."""
    provider_name = "JINA"

    def __init__(self, model_name: str = "jina-embeddings-v2-base-en") -> None:
        self.model_name = model_name

    def embed_query(self, text: str) -> List[float]:
        return BGEProvider(self.model_name).embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return BGEProvider(self.model_name).embed_documents(texts)


def get_embedding_provider(model_override: Optional[str] = None) -> EmbeddingProvider:
    """Factory function returning configured EmbeddingProvider instance."""
    settings = get_settings()
    model_name = model_override or settings.EMBEDDING_MODEL

    if "e5" in model_name.lower():
        return E5Provider(model_name)
    elif "jina" in model_name.lower():
        return JinaProvider(model_name)
    else:
        return BGEProvider(model_name)
