"""Core configuration settings using Pydantic Settings."""

import os
from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable fallback."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Server Configuration
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "ktu_ai_eval_super_secret_jwt_key_change_in_production_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_evaluation.db"

    # Model Provider Settings (Configurable via .env)
    OCR_ENGINE: str = Field(default="PADDLE", description="PADDLE, TROCR, EASYOCR, GOOGLE_VISION, MISTRAL")
    LLM_PROVIDER: str = Field(default="OLLAMA", description="OLLAMA, GEMINI, CLAUDE, OPENAI, QWEN, DEEPSEEK, LLAMA")
    LLM_MODEL: str = Field(default="qwen3", description="qwen3, gemma3, deepseek-r1:8b, llama3.2, etc.")
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    EMBEDDING_MODEL: str = Field(default="BAAI/bge-small-en-v1.5", description="BAAI/bge-small-en-v1.5, etc.")
    VECTOR_DB: str = Field(default="CHROMA", description="CHROMA, FAISS, MILVUS")
    CHROMA_PERSIST_DIR: str = "./vector_db/chroma"

    # Optional Cloud API Keys
    ALLOW_CLOUD_LLM: bool = Field(default=False, description="Explicit authorization required for external cloud LLMs")
    REFINEMENT_ENABLED: bool = Field(default=True, description="Enable LLM-assisted OCR refinement")
    REFINEMENT_TIMEOUT_SECONDS: float = Field(default=30.0, description="Max timeout in seconds for LLM refinement")
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Evaluation Thresholds & Configurable Grading Weights
    CONFIDENCE_THRESHOLD: float = 0.70

    CONCEPT_WEIGHT: float = Field(default=0.30, description="Weight for concept understanding")
    CORRECTNESS_WEIGHT: float = Field(default=0.20, description="Weight for correctness")
    COMPLETENESS_WEIGHT: float = Field(default=0.20, description="Weight for completeness")
    KEYWORD_WEIGHT: float = Field(default=0.10, description="Weight for keyword coverage")
    SEMANTIC_WEIGHT: float = Field(default=0.20, description="Weight for semantic embedding similarity")

    # KTU Theory Subjects
    KTU_DEFAULT_SUBJECTS: str = "Constitution of India,Industrial Economics,Professional Ethics"

    @property
    def subject_list(self) -> List[str]:
        """Return list of supported KTU theory subjects."""
        return [s.strip() for s in self.KTU_DEFAULT_SUBJECTS.split(",") if s.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton instance."""
    return Settings()
