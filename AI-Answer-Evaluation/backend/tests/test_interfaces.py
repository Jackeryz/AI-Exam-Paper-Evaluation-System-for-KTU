"""Unit tests for model-agnostic provider interfaces."""

import pytest
from app.services.ocr import get_ocr_service, TrOCRService, PaddleOCRService
from app.services.llm import get_llm_provider, OllamaProvider
from app.services.embedding import get_embedding_provider, BGEProvider
from app.services.vector_store import get_vector_store, ChromaVectorStore, VectorDocument


def test_ocr_provider_factory():
    service = get_ocr_service("PADDLE")
    assert isinstance(service, PaddleOCRService)

    trocr = get_ocr_service("TROCR")
    assert isinstance(trocr, TrOCRService)


@pytest.mark.anyio
async def test_llm_provider_factory():
    provider = get_llm_provider("OLLAMA", model_override="qwen3")
    assert isinstance(provider, OllamaProvider)
    response = await provider.generate("Test prompt")
    assert response.content is not None
    assert response.provider == "OLLAMA"


def test_embedding_provider_factory():
    provider = get_embedding_provider("BAAI/bge-small-en-v1.5")
    assert isinstance(provider, BGEProvider)
    vec = provider.embed_query("Constitution of India")
    assert isinstance(vec, list)
    assert len(vec) > 0


def test_vector_store_factory():
    store = get_vector_store("CHROMA")
    assert isinstance(store, ChromaVectorStore)
    docs = [VectorDocument(doc_id="doc_1", content="Article 14 guarantees equality before law.")]
    ids = store.add_documents("test_col", docs)
    assert ids == ["doc_1"]

    results = store.search("test_col", "equality before law")
    assert len(results) > 0
    assert results[0].doc_id == "doc_1"
