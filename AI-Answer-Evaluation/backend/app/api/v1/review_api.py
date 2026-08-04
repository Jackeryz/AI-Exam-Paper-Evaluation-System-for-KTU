"""Teacher Review & Override API v1 router."""

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.teacher_review.review_manager import TeacherReviewManager, ReviewOverrideRequest

router = APIRouter(prefix="/reviews", tags=["Teacher Review"])


@router.post("/override", response_model=Dict[str, Any])
async def submit_teacher_override(request: ReviewOverrideRequest):
    """Submit teacher manual score/feedback override for flagged evaluation."""
    manager = TeacherReviewManager()
    result = manager.save_teacher_override(
        override=request,
        original_marks=7.0,
        original_feedback="AI initial evaluation.",
    )
    return {"status": "SUCCESS", "review_record": result}
