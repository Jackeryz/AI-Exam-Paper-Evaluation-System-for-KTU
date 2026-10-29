"""Pydantic schemas for Answer Sheets, OCR, Extracted Answers, Evaluation, Feedback, and Analytics."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ExtractedAnswerResponse(BaseModel):
    id: int
    answer_sheet_id: int
    question_id: Optional[int] = None
    question_number: str
    raw_ocr_text: str
    refined_text: Optional[str] = None
    corrected_text: Optional[str] = None
    is_manually_corrected: bool = False
    uncertain_spans: List[Dict[str, Any]] = []
    page_number: int = 1

    class Config:
        from_attributes = True


class AnswerSheetResponse(BaseModel):
    id: int
    exam_id: int
    student_id: Optional[int] = None
    student_identifier: Optional[str] = None
    original_filename: Optional[str] = None
    file_path: str
    page_count: int = 1
    status: str
    error_message: Optional[str] = None
    raw_ocr_text: Optional[str] = None
    refined_ocr_text: Optional[str] = None
    corrected_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    refinement_provider: Optional[str] = None
    refinement_model: Optional[str] = None
    refinement_status: Optional[str] = None
    refinement_error: Optional[str] = None
    proposed_changes: List[Dict[str, Any]] = []
    uncertain_spans: List[Dict[str, Any]] = []
    is_teacher_approved: bool = False
    uploaded_at: datetime
    extracted_answers: List[ExtractedAnswerResponse] = []

    class Config:
        from_attributes = True


class OCRCorrectionRequest(BaseModel):
    corrected_text: Optional[str] = None
    refined_text: Optional[str] = None
    extracted_answer_id: Optional[int] = None
    action: Optional[str] = "SAVE_CORRECTION"  # SAVE_CORRECTION, ACCEPT_REFINEMENT, REVERT_TO_RAW


class OCRApprovalRequest(BaseModel):
    action: str = "ACCEPT_REFINEMENT"  # ACCEPT_REFINEMENT, REVERT_TO_RAW, MANUAL_EDIT
    edited_text: Optional[str] = None


class CriterionDeductionResponse(BaseModel):
    criterion: str
    allocated_marks: float
    awarded_marks: float
    deducted_marks: float
    reason: str
    evidence: Optional[str] = None



class EvaluationResponse(BaseModel):
    id: int
    answer_sheet_id: int
    question_id: int
    student_identifier: Optional[str] = None
    question_number: Optional[str] = None
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

    # Structured Criterion Evaluation & Methodology Traceability
    points_addressed: List[str] = []
    missing_points: List[str] = []
    identified_contradictions: List[str] = []
    evaluation_method: str = "DETERMINISTIC_HEURISTIC_FALLBACK"

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
