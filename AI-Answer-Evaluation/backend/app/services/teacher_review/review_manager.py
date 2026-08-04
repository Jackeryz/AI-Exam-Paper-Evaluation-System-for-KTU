"""Teacher Review & Oversight System handling confidence flagging (<70%), manual overrides, and dataset persistence."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.core.logging import logger


class ReviewOverrideRequest(BaseModel):
    evaluation_id: int
    teacher_id: int
    teacher_marks: float
    teacher_feedback: Optional[str] = None
    comments: Optional[str] = None


class TeacherReviewManager:
    """Manages manual review queue and teacher feedback overrides."""

    def flag_low_confidence(self, confidence_score: float, threshold: float = 0.70) -> bool:
        """Flag evaluation if confidence falls below threshold."""
        return confidence_score < threshold

    def save_teacher_override(
        self,
        override: ReviewOverrideRequest,
        original_marks: float,
        original_feedback: str,
    ) -> Dict[str, Any]:
        """Save teacher correction and record in feedback loop dataset."""
        record = {
            "evaluation_id": override.evaluation_id,
            "teacher_id": override.teacher_id,
            "original_marks": original_marks,
            "teacher_marks": override.teacher_marks,
            "original_feedback": original_feedback,
            "teacher_feedback": override.teacher_feedback or original_feedback,
            "comments": override.comments or "Teacher approved manual adjustment.",
            "reviewed_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Saved teacher override for evaluation {override.evaluation_id}: "
            f"Marks adjusted from {original_marks} to {override.teacher_marks}."
        )

        return record
