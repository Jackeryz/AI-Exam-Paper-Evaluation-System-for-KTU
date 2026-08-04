# Architecture & System Boundaries

## Overview

The **KTU AI Handwritten Answer Evaluation Platform** is built using a modular, provider-agnostic service-oriented architecture designed for scalability, maintainability, and academic research publication.

The system evaluates handwritten student answer sheets for theory-oriented KTU engineering subjects (such as *Constitution of India*, *Industrial Economics*, and *Professional Ethics*) without relying on fixed model implementations.

```
                  ┌─────────────────────────────────────────┐
                  │           FastAPI REST Server           │
                  └────────────────────┬────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
  ┌──────────────┐              ┌──────────────┐              ┌──────────────┐
  │ OCR Service  │              │ RAG Service  │              │ LLM Provider │
  │  Interface   │              │  (ChromaDB)  │              │  Interface   │
  └──────┬───────┘              └──────┬───────┘              └──────┬───────┘
         │                             │                             │
  ┌──────┴───────┐              ┌──────┴───────┐              ┌──────┴───────┐
  │ PaddleOCR    │              │ Embedding    │              │ Ollama /     │
  │ Sandbox      │              │ Provider     │              │ Local LLM    │
  └──────────────┘              └──────────────┘              └──────────────┘
```

## Component Boundaries

1. **OCR Layer (`backend/app/services/ocr/`)**:
   - Standardized via `OCRInterface`.
   - Primary engine wraps the local PaddleOCR sandbox (`experiments/ocr_sandbox/`) offline models.
   - Plug-and-play support for TrOCR, EasyOCR, Google Vision, and Mistral OCR.

2. **Refinement Engine (`backend/app/services/ocr_refinement/`)**:
   - Performs LLM cleanup on raw OCR text to correct obvious transcription errors.
   - Strictly enforces rules: no paraphrasing, no grammar modifications, no content additions.

3. **RAG & Context Retrieval (`backend/app/services/rag/`)**:
   - Indexes Question Papers, Answer Keys, Rubrics, and Study Notes into ChromaDB.
   - Uses `EmbeddingProvider` (default: `BAAI/bge-small-en-v1.5`) for semantic search.

4. **Ideal Answer Generator (`backend/app/services/ideal_answer/`)**:
   - Synthesizes reference ideal answers from multi-source context (Question + Key + Rubric + Notes + RAG).

5. **AI Grading Engine (`backend/app/services/grading_engine/`)**:
   - Evaluates Concept Understanding, Correctness, Completeness, Keyword Coverage, and Semantic Similarity.
   - Outputs question-wise scores, confidence ratings, and detailed feedback.

6. **Teacher Review System (`backend/app/services/teacher_review/`)**:
   - Automatically flags evaluations with confidence < 70% for manual teacher oversight.
   - Records overrides in a feedback dataset loop for future research.

7. **Database & Storage**:
   - SQLAlchemy async ORM with SQLite / PostgreSQL support.
   - Role-based JWT security (`Teacher`, `Student`, `Admin`).
