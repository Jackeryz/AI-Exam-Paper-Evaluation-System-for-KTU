"""Exams API v1 router for creating exams, uploading question papers, answer keys, rubrics & study material."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.session import get_db
from app.models.exam import Exam, Question, AnswerKey, Rubric, StudyMaterial
from app.schemas.exam import ExamCreate, ExamResponse, QuestionResponse
from app.core.security import oauth2_scheme, decode_token

router = APIRouter(prefix="/exams", tags=["Exams & Materials"])


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_in: ExamCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Create a new KTU Exam instance."""
    payload = decode_token(token)
    teacher_id = payload.get("user_id", 1)

    new_exam = Exam(
        title=exam_in.title,
        subject=exam_in.subject,
        semester=exam_in.semester,
        academic_year=exam_in.academic_year,
        teacher_id=teacher_id,
    )
    db.add(new_exam)
    await db.commit()
    await db.refresh(new_exam)

    if exam_in.questions:
        for q in exam_in.questions:
            question_obj = Question(
                exam_id=new_exam.id,
                question_number=q.question_number,
                text=q.text,
                max_marks=q.max_marks,
                subquestion_of=q.subquestion_of,
            )
            db.add(question_obj)
            await db.commit()
            await db.refresh(question_obj)

            if q.ideal_solution:
                ak = AnswerKey(
                    question_id=question_obj.id,
                    ideal_solution=q.ideal_solution,
                    keywords=q.keywords or [],
                )
                db.add(ak)

            if q.rubric_criteria:
                rub = Rubric(
                    question_id=question_obj.id,
                    criteria_json=q.rubric_criteria,
                )
                db.add(rub)

        await db.commit()
        await db.refresh(new_exam)

    return new_exam


@router.get("", response_model=List[ExamResponse])
async def list_exams(db: AsyncSession = Depends(get_db)):
    """List all configured exams."""
    result = await db.execute(select(Exam))
    return result.scalars().all()


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    """Get exam details by ID."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam
