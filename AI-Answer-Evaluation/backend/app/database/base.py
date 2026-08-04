"""SQLAlchemy metadata registry for all models."""

from app.database.session import Base
from app.models.user import User
from app.models.exam import Exam, Question, Rubric, AnswerKey, StudyMaterial
from app.models.evaluation import AnswerSheet, OCRResult, Evaluation, Feedback, Analytics

__all__ = [
    "Base",
    "User",
    "Exam",
    "Question",
    "Rubric",
    "AnswerKey",
    "StudyMaterial",
    "AnswerSheet",
    "OCRResult",
    "Evaluation",
    "Feedback",
    "Analytics",
]
