"""SQLAlchemy models for AnswerSheets, OCRResults, Evaluations, Feedback, and Analytics."""

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Float, Boolean, JSON
from sqlalchemy.orm import relationship

from app.database.session import Base


class AnswerSheet(Base):
    """Uploaded student answer script document."""

    __tablename__ = "answer_sheets"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    status = Column(String(50), default="UPLOADED")  # UPLOADED, OCR_PROCESSED, SEGMENTED, EVALUATED, REVIEWED
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    exam = relationship("Exam", back_populates="answer_sheets")
    student = relationship("User", back_populates="answer_sheets")
    ocr_result = relationship("OCRResult", back_populates="answer_sheet", uselist=False, cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="answer_sheet", cascade="all, delete-orphan")


class OCRResult(Base):
    """OCR output and LLM refinement result for an AnswerSheet."""

    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True, index=True)
    answer_sheet_id = Column(Integer, ForeignKey("answer_sheets.id"), nullable=False, unique=True)
    raw_text = Column(Text, nullable=False)
    refined_text = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)
    engine_used = Column(String(50), default="PADDLE")
    diff_json = Column(JSON, default=dict)
    bounding_boxes_json = Column(JSON, default=list)

    # Relationships
    answer_sheet = relationship("AnswerSheet", back_populates="ocr_result")


class Evaluation(Base):
    """AI evaluation result per student question response."""

    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    answer_sheet_id = Column(Integer, ForeignKey("answer_sheets.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    student_answer_text = Column(Text, nullable=True)
    ideal_answer_generated = Column(Text, nullable=True)
    marks_awarded = Column(Float, nullable=False, default=0.0)
    max_marks = Column(Float, nullable=False, default=10.0)
    feedback = Column(Text, nullable=True)
    improvement_suggestions = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    is_flagged = Column(Boolean, default=False)  # True if confidence < 70%
    is_reviewed = Column(Boolean, default=False)

    # Research Telemetry & Explainable Deductions Breakdown
    criterion_deductions_json = Column(JSON, default=list)
    strengths_json = Column(JSON, default=list)
    weaknesses_json = Column(JSON, default=list)
    deduction_reasons_json = Column(JSON, default=list)
    overall_summary = Column(Text, nullable=True)

    graded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    answer_sheet = relationship("AnswerSheet", back_populates="evaluations")
    question = relationship("Question", back_populates="evaluations")
    teacher_feedback = relationship("Feedback", back_populates="evaluation", uselist=False, cascade="all, delete-orphan")


class Feedback(Base):
    """Teacher override & review feedback record."""

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False, unique=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_marks = Column(Float, nullable=False)
    teacher_marks = Column(Float, nullable=False)
    original_feedback = Column(Text, nullable=True)
    teacher_feedback = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    evaluation = relationship("Evaluation", back_populates="teacher_feedback")


class Analytics(Base):
    """Calculated exam-level analytics summary."""

    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    average_marks = Column(Float, default=0.0)
    highest_marks = Column(Float, default=0.0)
    lowest_marks = Column(Float, default=0.0)
    weak_topics_json = Column(JSON, default=list)
    difficulty_distribution_json = Column(JSON, default=dict)
    generated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    exam = relationship("Exam", back_populates="analytics")
