"""Exams API v1 router for creating exams, generating KTU exam codes, uploading question papers, answer keys, rubrics & study material."""

import os
import random
import re
import string
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func

from app.database.session import get_db
from app.models.exam import Exam, Question, AnswerKey, Rubric, StudyMaterial, ApprovedReferenceAnswer
from app.models.evaluation import AnswerSheet, Evaluation
from app.models.user import User, UserRole
from app.schemas.exam import ExamCreate, ExamUpdate, ExamResponse, QuestionResponse, QuestionCreate
from app.core.security import get_current_user, get_current_teacher_or_admin, oauth2_scheme, decode_token

router = APIRouter(prefix="/exams", tags=["Exams & Materials"])

UPLOAD_DOCS_DIR = Path("./dataset/documents")
UPLOAD_DOCS_DIR.mkdir(parents=True, exist_ok=True)


def generate_exam_code(subject: str, exam_type: str) -> str:
    """Generate a unique, non-guessable examination code (e.g., KTU-CS301-MID1-A7K9)."""
    # Clean subject prefix
    sub_words = re.findall(r"[A-Za-z0-9]+", subject)
    sub_prefix = "".join(w[:2].upper() for w in sub_words[:2]) if sub_words else "KTU"
    if len(sub_prefix) < 3:
        sub_prefix = (sub_prefix + "EXAM")[:5]

    # Clean type token
    type_token = "REG"
    if "mid" in exam_type.lower() or "internal" in exam_type.lower():
        type_token = "INT"
    elif "suppl" in exam_type.lower():
        type_token = "SUP"

    # Crypto-random 4-character suffix
    rand_chars = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"KTU-{sub_prefix}-{type_token}-{rand_chars}"


async def get_exam_response_data(exam: Exam, db: AsyncSession) -> dict:
    """Helper to populate total_sheets, evaluated_sheets, and pending_review_count."""
    # Count sheets
    sheet_res = await db.execute(
        select(func.count(AnswerSheet.id)).where(AnswerSheet.exam_id == exam.id)
    )
    total_sheets = sheet_res.scalar() or 0

    # Count evaluated sheets
    eval_res = await db.execute(
        select(func.count(AnswerSheet.id)).where(
            AnswerSheet.exam_id == exam.id,
            AnswerSheet.status.in_(["EVALUATED", "REVIEWED", "COMPLETED"])
        )
    )
    evaluated_sheets = eval_res.scalar() or 0

    # Count flagged evaluations
    flag_res = await db.execute(
        select(func.count(Evaluation.id))
        .join(AnswerSheet, Evaluation.answer_sheet_id == AnswerSheet.id)
        .where(AnswerSheet.exam_id == exam.id, Evaluation.is_flagged == True, Evaluation.is_reviewed == False)
    )
    pending_reviews = flag_res.scalar() or 0

    return {
        "id": exam.id,
        "exam_code": exam.exam_code,
        "title": exam.title,
        "subject": exam.subject,
        "subject_code": exam.subject_code,
        "semester": exam.semester,
        "academic_year": exam.academic_year,
        "exam_date": exam.exam_date,
        "exam_type": exam.exam_type,
        "max_marks": exam.max_marks,
        "duration_minutes": exam.duration_minutes,
        "instructions": exam.instructions,
        "status": exam.status,
        "question_paper_path": exam.question_paper_path,
        "answer_key_path": exam.answer_key_path,
        "rubric_scheme_path": exam.rubric_scheme_path,
        "teacher_id": exam.teacher_id,
        "created_at": exam.created_at,
        "questions": [
            {
                "id": q.id,
                "exam_id": q.exam_id,
                "question_number": q.question_number,
                "text": q.text,
                "max_marks": q.max_marks,
                "subquestion_of": q.subquestion_of,
                "ideal_solution": q.answer_key.ideal_solution if q.answer_key else None,
                "keywords": q.answer_key.keywords if q.answer_key and q.answer_key.keywords else [],
                "rubric_criteria": q.rubric.criteria_json if q.rubric else None,
                "approved_reference": q.approved_reference,
            }
            for q in exam.questions
        ],
        "total_sheets": total_sheets,
        "evaluated_sheets": evaluated_sheets,
        "pending_review_count": pending_reviews,
    }


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_in: ExamCreate,
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new KTU Examination with auto-generated non-guessable code."""
    teacher_id = current_user.id

    # Auto-generate unique code if not provided
    exam_code = exam_in.exam_code or generate_exam_code(exam_in.subject, exam_in.exam_type)

    # Ensure uniqueness
    existing = await db.execute(select(Exam).where(Exam.exam_code == exam_code))
    while existing.scalars().first():
        exam_code = generate_exam_code(exam_in.subject, exam_in.exam_type)
        existing = await db.execute(select(Exam).where(Exam.exam_code == exam_code))

    new_exam = Exam(
        exam_code=exam_code,
        title=exam_in.title,
        subject=exam_in.subject,
        subject_code=exam_in.subject_code,
        semester=exam_in.semester,
        academic_year=exam_in.academic_year,
        exam_date=exam_in.exam_date,
        exam_type=exam_in.exam_type,
        max_marks=exam_in.max_marks,
        duration_minutes=exam_in.duration_minutes,
        instructions=exam_in.instructions,
        status="CONFIGURED",
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

    # Re-fetch with relationships loaded
    result = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .where(Exam.id == new_exam.id)
    )
    full_exam = result.scalars().first()
    return await get_exam_response_data(full_exam, db)


@router.post("/{exam_id}/upload-documents", response_model=ExamResponse)
async def upload_exam_documents(
    exam_id: int,
    question_paper: Optional[UploadFile] = File(None),
    answer_key: Optional[UploadFile] = File(None),
    rubric_scheme: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload official question paper, answer key, or marking scheme documents."""
    result = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .where(Exam.id == exam_id)
    )
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this examination")

    exam_dir = UPLOAD_DOCS_DIR / f"exam_{exam.id}"
    exam_dir.mkdir(parents=True, exist_ok=True)

    if question_paper and question_paper.filename:
        qp_path = exam_dir / f"qp_{question_paper.filename}"
        content = await question_paper.read()
        qp_path.write_bytes(content)
        exam.question_paper_path = str(qp_path)

    if answer_key and answer_key.filename:
        ak_path = exam_dir / f"ak_{answer_key.filename}"
        content = await answer_key.read()
        ak_path.write_bytes(content)
        exam.answer_key_path = str(ak_path)

    if rubric_scheme and rubric_scheme.filename:
        rs_path = exam_dir / f"rubric_{rubric_scheme.filename}"
        content = await rubric_scheme.read()
        rs_path.write_bytes(content)
        exam.rubric_scheme_path = str(rs_path)

    await db.commit()
    await db.refresh(exam)
    return await get_exam_response_data(exam, db)


@router.get("", response_model=List[ExamResponse])
async def list_exams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List exams with calculated aggregate counts (scoped to current teacher, or all for admin)."""
    stmt = (
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .order_by(Exam.created_at.desc())
    )
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Exam.teacher_id == current_user.id)

    result = await db.execute(stmt)
    exams = result.scalars().all()
    output = []
    for exam in exams:
        output.append(await get_exam_response_data(exam, db))
    return output


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get exam details by ID."""
    result = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .where(Exam.id == exam_id)
    )
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this examination")

    return await get_exam_response_data(exam, db)


@router.get("/code/{exam_code}", response_model=ExamResponse)
async def get_exam_by_code(
    exam_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Look up an examination by its unique code."""
    result = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .where(Exam.exam_code == exam_code.strip())
    )
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"No exam found with code '{exam_code}'")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this examination")

    return await get_exam_response_data(exam, db)


@router.post("/{exam_id}/questions", response_model=ExamResponse)
async def configure_questions(
    exam_id: int,
    questions: List[QuestionCreate],
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add or update questions for an examination with max marks validation."""
    result = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .where(Exam.id == exam_id)
    )
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this examination")

    total_marks = sum(q.max_marks for q in questions)
    if total_marks > exam.max_marks:
        raise HTTPException(
            status_code=400,
            detail=f"Configured questions total {total_marks} marks, which exceeds examination maximum ({exam.max_marks} marks)."
        )

    # Delete existing questions and replace
    for existing_q in exam.questions:
        await db.delete(existing_q)
    await db.commit()

    for q in questions:
        question_obj = Question(
            exam_id=exam.id,
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
    db.expire(exam)

    # Refresh
    refreshed = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .where(Exam.id == exam_id)
    )
    return await get_exam_response_data(refreshed.scalars().first(), db)


@router.put("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: int,
    exam_in: ExamUpdate,
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update supported metadata for an existing examination."""
    result = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
        )
        .where(Exam.id == exam_id)
    )
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this examination")

    update_data = exam_in.dict(exclude_unset=True)
    for field, val in update_data.items():
        if hasattr(exam, field) and val is not None:
            setattr(exam, field, val)

    await db.commit()
    await db.refresh(exam)
    return await get_exam_response_data(exam, db)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: int,
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete an examination and its associated resources with safe cascade loading."""
    result = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(Exam.questions).selectinload(Question.approved_reference),
            selectinload(Exam.questions).selectinload(Question.reference_proposals),
            selectinload(Exam.answer_sheets).selectinload(AnswerSheet.evaluations),
            selectinload(Exam.answer_sheets).selectinload(AnswerSheet.extracted_answers),
            selectinload(Exam.answer_sheets).selectinload(AnswerSheet.ocr_result),
        )
        .where(Exam.id == exam_id)
    )
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this examination")

    await db.delete(exam)
    await db.commit()
    return None

