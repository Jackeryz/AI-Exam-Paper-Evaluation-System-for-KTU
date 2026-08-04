"""Backward-compatibility wrapper for AIGradingEngine delegating to app.services.grading."""

from typing import Any, Dict, List, Optional

from app.services.grading import (
    EvaluatorOrchestrator,
    GradingResult,
    ScoreBreakdown as GradingBreakdown,
)
from app.services.llm.llm_interface import LLMProvider
from app.services.embedding.embedding_interface import EmbeddingProvider


class AIGradingEngine:
    """Backward-compatible wrapper delegating to the refactored EvaluatorOrchestrator."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.orchestrator = EvaluatorOrchestrator(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )

    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity (0 to 10 scale)."""
        vec1 = self.orchestrator.embedding_provider.embed_query(text1)
        vec2 = self.orchestrator.embedding_provider.embed_query(text2)
        sim = self.orchestrator.score_aggregator.weights.semantic_weight
        from app.services.grading.grading_metrics import GradingMetrics
        cos = GradingMetrics.cosine_similarity(vec1, vec2)
        return round(cos * 10.0, 2)

    async def evaluate_answer(
        self,
        question_number: str,
        student_answer: str,
        ideal_answer: str,
        max_marks: float = 10.0,
        keywords: Optional[List[str]] = None,
    ) -> GradingResult:
        """Backward-compatible evaluation interface."""
        rubric_dict = {"mandatory_keywords": keywords or []} if keywords else None
        return await self.orchestrator.evaluate(
            question_number=question_number,
            question_text=f"Question {question_number}",
            student_answer=student_answer,
            ideal_answer=ideal_answer,
            rubric_data=rubric_dict,
            max_marks=max_marks,
        )
