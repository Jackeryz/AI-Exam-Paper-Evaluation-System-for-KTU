"""RAG Engine for document chunking, ChromaDB vector indexing, and context retrieval."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.core.logging import logger
from app.services.vector_store.vector_store_interface import (
    get_vector_store,
    VectorDocument,
    SearchResult,
    VectorStoreInterface,
)


class RAGContext(BaseModel):
    question_number: str
    relevant_rubric: str
    relevant_answer_key: str
    study_notes_context: List[str]


class RAGEngine:
    """Document Ingestion & Context Retrieval Engine for AI Answer Evaluation."""

    def __init__(self, vector_store: Optional[VectorStoreInterface] = None) -> None:
        self.vector_store = vector_store or get_vector_store()

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Simple sliding window chunker."""
        words = text.split()
        if not words:
            return []
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
        return chunks

    def ingest_study_material(self, exam_id: int, doc_id: str, title: str, text: str) -> int:
        """Chunk and index study notes into ChromaDB."""
        chunks = self.chunk_text(text)
        vector_docs = [
            VectorDocument(
                doc_id=f"{doc_id}_chunk_{idx}",
                content=chunk,
                metadata={"exam_id": exam_id, "title": title, "chunk_idx": idx},
            )
            for idx, chunk in enumerate(chunks)
        ]
        self.vector_store.add_documents(f"exam_{exam_id}_study_material", vector_docs)
        logger.info(f"Ingested {len(chunks)} study material chunks for exam {exam_id}.")
        return len(chunks)

    def retrieve_context(
        self,
        exam_id: int,
        question_number: str,
        question_text: str,
        answer_key_text: str,
        rubric_text: str,
    ) -> RAGContext:
        """Retrieve relevant study notes and combine with question metadata."""
        search_results = self.vector_store.search(
            collection_name=f"exam_{exam_id}_study_material",
            query=f"{question_number} {question_text}",
            top_k=3,
        )
        notes = [res.content for res in search_results]

        return RAGContext(
            question_number=question_number,
            relevant_rubric=rubric_text or "General scoring based on concept clarity and keywords.",
            relevant_answer_key=answer_key_text or "No model answer provided.",
            study_notes_context=notes,
        )
