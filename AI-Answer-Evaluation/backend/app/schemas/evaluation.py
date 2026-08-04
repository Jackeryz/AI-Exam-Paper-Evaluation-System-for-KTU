"""Pydantic schemas for Answer Sheets, OCR, Evaluation, Feedback, and Analytics."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AnswerSheetResponse(BaseModel):
    id: int
    exam_id: int
    student_id: int
    file_path: str
    status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class CriterionDeductionResponse(BaseModel):
    criterion: str
    allocated_marks: float
    awarded_marks: float
    deducted_marks: float
    reason: str


class EvaluationResponse(BaseModel):
    id: int
    answer_sheet_id: int
    question_id: int
    student_answer_text: Optional[str] = None
    ideal_answer_generated: Optional[str] = None
    marks_awarded: float
    max_marks: float
    feedback: Optional[str] = None
    improvement_suggestions: Optional[str] = None
    confidence_score: float
    is_flagged: bool
    is_reviewed: bool

    # Explainable Feedback & Criterion Deductions Breakdown
    criterion_deductions: List[CriterionDeductionResponse] = []
    strengths: List[str] = []
    weaknesses: List[str] = []
    reasons_for_deduction: List[str] = []
    overall_summary: Optional[str] = None

    graded_at: datetime

    class Config:
        from_attributes = True


class EvaluationOverride(BaseModel):
    evaluation_id: int
    teacher_marks: float
    teacher_feedback: Optional[str] = None
    comments: Optional[str] = None


class AnalyticsResponse(BaseModel):
    exam_id: int
    average_marks: float
    highest_marks: float
    lowest_marks: float
    weak_topics: List[str]
    difficulty_distribution: Dict[str, Any]
    generated_at: datetime
