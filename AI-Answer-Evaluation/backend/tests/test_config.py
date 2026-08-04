"""Unit tests for system configuration and settings."""

import os
from app.core.config import get_settings, Settings


def test_settings_defaults():
    """Verify system default configurations."""
    settings = get_settings()
    assert settings.OCR_ENGINE == "PADDLE"
    assert settings.LLM_PROVIDER == "OLLAMA"
    assert settings.LLM_MODEL == "qwen3"
    assert settings.EMBEDDING_MODEL == "BAAI/bge-small-en-v1.5"
    assert settings.VECTOR_DB == "CHROMA"
    assert settings.CONFIDENCE_THRESHOLD == 0.70
    assert "Constitution of India" in settings.subject_list
