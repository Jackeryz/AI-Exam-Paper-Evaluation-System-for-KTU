"""Pydantic schemas for Exams, Questions, Rubrics, and Answer Keys."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class QuestionBase(BaseModel):
    question_number: str
    text: str
    max_marks: float = 10.0
    subquestion_of: Optional[str] = None


class QuestionCreate(QuestionBase):
    ideal_solution: Optional[str] = None
    keywords: Optional[List[str]] = None
    rubric_criteria: Optional[Dict[str, Any]] = None


class QuestionResponse(QuestionBase):
    id: int
    exam_id: int

    class Config:
        from_attributes = True


class ExamBase(BaseModel):
    title: str
    subject: str
    semester: Optional[str] = None
    academic_year: Optional[str] = None


class ExamCreate(ExamBase):
    questions: Optional[List[QuestionCreate]] = None


class ExamResponse(ExamBase):
    id: int
    teacher_id: int
    created_at: datetime
    questions: List[QuestionResponse] = []

    class Config:
        from_attributes = True
