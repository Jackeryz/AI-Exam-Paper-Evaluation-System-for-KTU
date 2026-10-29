"""Pydantic schemas for Exams, Questions, Rubrics, Answer Keys, and Reference Answers."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QuestionBase(BaseModel):
    question_number: str
    text: str
    max_marks: float = 10.0
    subquestion_of: Optional[str] = None


class QuestionCreate(QuestionBase):
    ideal_solution: Optional[str] = None
    keywords: Optional[List[str]] = None
    rubric_criteria: Optional[Dict[str, Any]] = None


class ReferenceAnswerProposalResponse(BaseModel):
    id: int
    question_id: int
    provider: str
    model: str
    proposed_answer: str
    proposed_rubric_json: Dict[str, Any] = {}
    key_concepts_json: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ApprovedReferenceAnswerResponse(BaseModel):
    id: int
    question_id: int
    approved_answer: str
    approved_rubric_json: Dict[str, Any] = {}
    key_concepts_json: List[str] = []
    version: int = 1
    approved_at: datetime

    class Config:
        from_attributes = True


class QuestionResponse(QuestionBase):
    id: int
    exam_id: int
    ideal_solution: Optional[str] = None
    keywords: List[str] = []
    rubric_criteria: Optional[Dict[str, Any]] = None
    approved_reference: Optional[ApprovedReferenceAnswerResponse] = None

    class Config:
        from_attributes = True


class ExamBase(BaseModel):
    title: str
    subject: str
    subject_code: Optional[str] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    exam_date: Optional[str] = None
    exam_type: str = "Regular End-Semester"
    max_marks: float = 100.0
    duration_minutes: Optional[int] = 180
    instructions: Optional[str] = None


class ExamCreate(ExamBase):
    exam_code: Optional[str] = None  # Auto-generated if not provided
    questions: Optional[List[QuestionCreate]] = None


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    subject: Optional[str] = None
    subject_code: Optional[str] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    exam_date: Optional[str] = None
    exam_type: Optional[str] = None
    max_marks: Optional[float] = None
    duration_minutes: Optional[int] = None
    instructions: Optional[str] = None
    status: Optional[str] = None


class ExamResponse(ExamBase):
    id: int
    exam_code: str
    teacher_id: int
    status: str = "CONFIGURED"
    question_paper_path: Optional[str] = None
    answer_key_path: Optional[str] = None
    rubric_scheme_path: Optional[str] = None
    created_at: datetime
    questions: List[QuestionResponse] = []
    total_sheets: int = 0
    evaluated_sheets: int = 0
    pending_review_count: int = 0

    class Config:
        from_attributes = True
