"""Embedding provider package."""

from app.services.embedding.embedding_interface import (
    EmbeddingProvider,
    BGEProvider,
    E5Provider,
    JinaProvider,
    get_embedding_provider,
)

__all__ = [
    "EmbeddingProvider",
    "BGEProvider",
    "E5Provider",
    "JinaProvider",
    "get_embedding_provider",
]
