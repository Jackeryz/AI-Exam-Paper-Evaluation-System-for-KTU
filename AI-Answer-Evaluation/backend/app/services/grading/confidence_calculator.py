"""Deterministic Confidence Calculator combining measurable system signals."""

from typing import Dict, Any
from pydantic import BaseModel, Field

from app.core.config import get_settings


class ConfidenceBreakdown(BaseModel):
    ocr_confidence_factor: float
    semantic_similarity_factor: float
    keyword_coverage_factor: float
    rag_relevance_factor: float
    json_validity_factor: float
    overall_confidence: float
    is_flagged: bool
    confidence_details: Dict[str, float] = Field(default_factory=dict)


class ConfidenceCalculator:
    """Computes deterministic evaluation confidence and triggers review flags."""

    def __init__(self, threshold: float = None) -> None:
        settings = get_settings()
        self.threshold = threshold or settings.CONFIDENCE_THRESHOLD

    def calculate(
        self,
        ocr_confidence: float,        # 0.0 to 1.0 from OCR result
        semantic_similarity: float,   # 0.0 to 1.0 ratio
        keyword_coverage: float,      # 0.0 to 1.0 ratio
        rag_relevance: float = 0.85,  # 0.0 to 1.0 document relevance
        is_json_valid: bool = True,
    ) -> ConfidenceBreakdown:
        """Compute overall confidence deterministically using measurable signals."""
        ocr_factor = max(0.0, min(1.0, ocr_confidence))
        sem_factor = max(0.0, min(1.0, semantic_similarity))
        kw_factor = max(0.0, min(1.0, keyword_coverage))
        rag_factor = max(0.0, min(1.0, rag_relevance))
        json_factor = 1.0 if is_json_valid else 0.40

        # Weighted confidence formula
        # OCR (25%), Semantic (25%), Keyword (25%), RAG (15%), JSON Validity (10%)
        overall = (
            (ocr_factor * 0.25) +
            (sem_factor * 0.25) +
            (kw_factor * 0.25) +
            (rag_factor * 0.15) +
            (json_factor * 0.10)
        )

        overall_clamped = float(round(max(0.0, min(1.0, overall)), 4))
        is_flagged = overall_clamped < self.threshold

        details = {
            "ocr_confidence": round(ocr_factor, 2),
            "semantic_similarity": round(sem_factor, 2),
            "keyword_coverage": round(kw_factor, 2),
            "rag_relevance": round(rag_factor, 2),
            "json_validity": round(json_factor, 2),
        }

        return ConfidenceBreakdown(
            ocr_confidence_factor=ocr_factor,
            semantic_similarity_factor=sem_factor,
            keyword_coverage_factor=kw_factor,
            rag_relevance_factor=rag_factor,
            json_validity_factor=json_factor,
            overall_confidence=overall_clamped,
            is_flagged=is_flagged,
            confidence_details=details,
        )
