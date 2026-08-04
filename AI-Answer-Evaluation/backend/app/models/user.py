"""SQLAlchemy models for User and Authentication."""

import enum
from datetime import datetime
from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship

from app.database.session import Base


class UserRole(str, enum.Enum):
    """User role enumeration for RBAC."""
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class User(Base):
    """User entity for Teachers, Students, and Admins."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.TEACHER, nullable=False)
    department = Column(String(100), default="KTU Engineering")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    exams = relationship("Exam", back_populates="teacher", cascade="all, delete-orphan")
    answer_sheets = relationship("AnswerSheet", back_populates="student", cascade="all, delete-orphan")
