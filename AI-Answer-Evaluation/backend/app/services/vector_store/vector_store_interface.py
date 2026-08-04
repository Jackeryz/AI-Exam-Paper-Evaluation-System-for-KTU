"""Vector Store Interface and implementations (Chroma, FAISS, Milvus)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import logger
from app.services.embedding.embedding_interface import get_embedding_provider, EmbeddingProvider


class VectorDocument(BaseModel):
    """Document payload stored in vector database."""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None


class SearchResult(BaseModel):
    """Result returned from vector similarity search."""
    doc_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VectorStoreInterface(ABC):
    """Abstract base class for modular vector store backends."""

    store_name: str

    @abstractmethod
    def add_documents(self, collection_name: str, documents: List[VectorDocument]) -> List[str]:
        """Add list of documents to a named collection."""
        pass

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Retrieve top-K most similar document chunks."""
        pass


class ChromaVectorStore(VectorStoreInterface):
    """ChromaDB local vector store implementation."""

    store_name = "CHROMA"

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        settings = get_settings()
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self._in_memory_store: Dict[str, List[VectorDocument]] = {}

    def add_documents(self, collection_name: str, documents: List[VectorDocument]) -> List[str]:
        if collection_name not in self._in_memory_store:
            self._in_memory_store[collection_name] = []

        ids = []
        for doc in documents:
            if not doc.embedding:
                doc.embedding = self.embedding_provider.embed_query(doc.content)
            self._in_memory_store[collection_name].append(doc)
            ids.append(doc.doc_id)

        logger.info(f"Added {len(documents)} documents to Chroma collection '{collection_name}'.")
        return ids

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        query_vec = self.embedding_provider.embed_query(query)
        docs = self._in_memory_store.get(collection_name, [])

        if not docs:
            return []

        results = []
        for doc in docs:
            if metadata_filter:
                match = all(doc.metadata.get(k) == v for k, v in metadata_filter.items())
                if not match:
                    continue

            doc_vec = doc.embedding or self.embedding_provider.embed_query(doc.content)
            # Cosine similarity calculation
            dot = sum(a * b for a, b in zip(query_vec, doc_vec))
            norm_a = sum(a * a for a in query_vec) ** 0.5
            norm_b = sum(b * b for b in doc_vec) ** 0.5
            score = dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0

            results.append(
                SearchResult(
                    doc_id=doc.doc_id,
                    content=doc.content,
                    score=float(score),
                    metadata=doc.metadata,
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]


class FAISSVectorStore(VectorStoreInterface):
    """FAISS Vector Store implementation stub."""
    store_name = "FAISS"

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None) -> None:
        self.chroma_fallback = ChromaVectorStore(embedding_provider=embedding_provider)

    def add_documents(self, collection_name: str, documents: List[VectorDocument]) -> List[str]:
        return self.chroma_fallback.add_documents(collection_name, documents)

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        return self.chroma_fallback.search(collection_name, query, top_k, metadata_filter)


class MilvusVectorStore(VectorStoreInterface):
    """Milvus Vector Store implementation stub."""
    store_name = "MILVUS"

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None) -> None:
        self.chroma_fallback = ChromaVectorStore(embedding_provider=embedding_provider)

    def add_documents(self, collection_name: str, documents: List[VectorDocument]) -> List[str]:
        return self.chroma_fallback.add_documents(collection_name, documents)

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        return self.chroma_fallback.search(collection_name, query, top_k, metadata_filter)


def get_vector_store(store_override: Optional[str] = None) -> VectorStoreInterface:
    """Factory function returning configured vector database store instance."""
    settings = get_settings()
    store_name = (store_override or settings.VECTOR_DB).upper()

    stores = {
        "CHROMA": ChromaVectorStore,
        "FAISS": FAISSVectorStore,
        "MILVUS": MilvusVectorStore,
    }

    store_class = stores.get(store_name, ChromaVectorStore)
    return store_class()
