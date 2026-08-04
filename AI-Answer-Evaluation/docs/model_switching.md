# Model Switching & Provider Configuration Guide

This platform is 100% model-agnostic. All providers can be swapped cleanly through environment configuration in `.env` without modifying any backend code.

## Environment Configuration (`.env`)

```env
# OCR Engine (PADDLE, TROCR, EASYOCR, GOOGLE_VISION, MISTRAL)
OCR_ENGINE=PADDLE

# LLM Provider (OLLAMA, GEMINI, CLAUDE, OPENAI, QWEN, DEEPSEEK, LLAMA)
LLM_PROVIDER=OLLAMA
LLM_MODEL=qwen3
OLLAMA_BASE_URL=http://localhost:11434

# Embedding Model (BAAI/bge-small-en-v1.5, intfloat/e5-small-v2, jina-embeddings-v2-base-en)
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Vector Store (CHROMA, FAISS, MILVUS)
VECTOR_DB=CHROMA
```

## Supported Local Models

- **OCR Engine**: Local PaddleOCR 3.x (`PP-OCRv5_mobile_det` & `en_PP-OCRv5_mobile_rec`).
- **LLM Models**: Local Ollama-compatible models (`qwen3`, `gemma3`, `deepseek-r1:8b`, `llama3.2`).
- **Embedding Model**: `BAAI/bge-small-en-v1.5`.
- **Vector Database**: Local ChromaDB.
