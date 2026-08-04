"""SQLAlchemy models for Exams, Questions, Rubrics, Answer Keys, and Study Materials."""

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Float, JSON
from sqlalchemy.orm import relationship

from app.database.session import Base


class Exam(Base):
    """Exam metadata model."""

    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(100), nullable=False)  # Constitution of India, Industrial Economics, etc.
    semester = Column(String(50), nullable=True)
    academic_year = Column(String(50), nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    teacher = relationship("User", back_populates="exams")
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    study_materials = relationship("StudyMaterial", back_populates="exam", cascade="all, delete-orphan")
    answer_sheets = relationship("AnswerSheet", back_populates="exam", cascade="all, delete-orphan")
    analytics = relationship("Analytics", back_populates="exam", cascade="all, delete-orphan")


class Question(Base):
    """Question paper question / subquestion entity."""

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    question_number = Column(String(50), nullable=False)  # e.g. "1(a)", "2(b)(i)"
    text = Column(Text, nullable=False)
    max_marks = Column(Float, nullable=False, default=10.0)
    subquestion_of = Column(String(50), nullable=True)

    # Relationships
    exam = relationship("Exam", back_populates="questions")
    answer_key = relationship("AnswerKey", back_populates="question", uselist=False, cascade="all, delete-orphan")
    rubric = relationship("Rubric", back_populates="question", uselist=False, cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="question")


class AnswerKey(Base):
    """Answer key reference text and keywords per question."""

    __tablename__ = "answer_keys"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, unique=True)
    ideal_solution = Column(Text, nullable=False)
    keywords = Column(JSON, default=list)  # Key technical terms/concepts
    model_answer = Column(Text, nullable=True)

    # Relationships
    question = relationship("Question", back_populates="answer_key")


class Rubric(Base):
    """Evaluation rubric criteria and marking scheme per question."""

    __tablename__ = "rubrics"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, unique=True)
    criteria_json = Column(JSON, default=dict)  # {"concept": 40%, "keywords": 30%, "completeness": 30%}
    scoring_guidelines = Column(Text, nullable=True)

    # Relationships
    question = relationship("Question", back_populates="rubric")


class StudyMaterial(Base):
    """Uploaded study materials, textbook notes, and reference context."""

    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    content_type = Column(String(50), default="pdf")
    extracted_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    exam = relationship("Exam", back_populates="study_materials")
