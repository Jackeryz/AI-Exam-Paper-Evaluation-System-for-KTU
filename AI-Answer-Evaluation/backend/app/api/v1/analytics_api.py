"""Analytics API v1 router for dashboard metrics and exam-level performance analytics."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, desc

from app.database.session import get_db
from app.models.exam import Exam, Question
from app.models.evaluation import AnswerSheet, Evaluation, Feedback
from app.models.user import User, UserRole
from app.core.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve live dashboard summary metrics for teacher view."""
    is_admin = (current_user.role == UserRole.ADMIN)

    # 1. Total Exams
    exam_stmt = select(func.count(Exam.id))
    if not is_admin:
        exam_stmt = exam_stmt.where(Exam.teacher_id == current_user.id)
    exam_count_res = await db.execute(exam_stmt)
    total_exams = exam_count_res.scalar() or 0

    # 2. Total Answer Sheets
    sheet_stmt = select(func.count(AnswerSheet.id)).join(Exam, AnswerSheet.exam_id == Exam.id)
    if not is_admin:
        sheet_stmt = sheet_stmt.where(Exam.teacher_id == current_user.id)
    sheet_count_res = await db.execute(sheet_stmt)
    total_answer_sheets = sheet_count_res.scalar() or 0

    # 3. Total Evaluations
    eval_stmt = (
        select(func.count(Evaluation.id))
        .join(AnswerSheet, Evaluation.answer_sheet_id == AnswerSheet.id)
        .join(Exam, AnswerSheet.exam_id == Exam.id)
    )
    if not is_admin:
        eval_stmt = eval_stmt.where(Exam.teacher_id == current_user.id)
    eval_count_res = await db.execute(eval_stmt)
    total_evaluations = eval_count_res.scalar() or 0

    # 4. Pending Reviews (Evaluations flagged or needing review)
    pending_stmt = (
        select(func.count(Evaluation.id))
        .join(AnswerSheet, Evaluation.answer_sheet_id == AnswerSheet.id)
        .join(Exam, AnswerSheet.exam_id == Exam.id)
        .where((Evaluation.is_flagged == True) & (Evaluation.is_reviewed == False))
    )
    if not is_admin:
        pending_stmt = pending_stmt.where(Exam.teacher_id == current_user.id)
    pending_res = await db.execute(pending_stmt)
    pending_reviews = pending_res.scalar() or 0

    # 5. Completed Evaluations (Reviewed or Approved with confidence >= 0.70)
    completed_stmt = (
        select(func.count(Evaluation.id))
        .join(AnswerSheet, Evaluation.answer_sheet_id == AnswerSheet.id)
        .join(Exam, AnswerSheet.exam_id == Exam.id)
        .where((Evaluation.is_reviewed == True) | (Evaluation.is_flagged == False))
    )
    if not is_admin:
        completed_stmt = completed_stmt.where(Exam.teacher_id == current_user.id)
    completed_res = await db.execute(completed_stmt)
    completed_evaluations = completed_res.scalar() or 0

    # 6. Recent Exams
    recent_exams_stmt = (
        select(Exam)
        .options(selectinload(Exam.answer_sheets))
        .order_by(desc(Exam.created_at))
        .limit(5)
    )
    if not is_admin:
        recent_exams_stmt = recent_exams_stmt.where(Exam.teacher_id == current_user.id)
    recent_exams_query = await db.execute(recent_exams_stmt)
    recent_exams_list = recent_exams_query.scalars().all()
    recent_exams_data = [
        {
            "id": ex.id,
            "title": ex.title,
            "course_code": ex.subject_code or "",
            "exam_code": ex.exam_code,
            "total_marks": ex.max_marks,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
            "sheet_count": len(ex.answer_sheets) if ex.answer_sheets else 0,
        }
        for ex in recent_exams_list
    ]

    # 7. Recent Evaluations
    recent_evals_stmt = (
        select(Evaluation)
        .join(AnswerSheet, Evaluation.answer_sheet_id == AnswerSheet.id)
        .join(Exam, AnswerSheet.exam_id == Exam.id)
        .options(
            selectinload(Evaluation.answer_sheet),
            selectinload(Evaluation.question)
        )
        .order_by(desc(Evaluation.graded_at))
        .limit(5)
    )
    if not is_admin:
        recent_evals_stmt = recent_evals_stmt.where(Exam.teacher_id == current_user.id)
    recent_evals_query = await db.execute(recent_evals_stmt)
    recent_evals_list = recent_evals_query.scalars().all()
    recent_evals_data = [
        {
            "id": ev.id,
            "sheet_id": ev.answer_sheet_id,
            "student_identifier": ev.answer_sheet.student_identifier if ev.answer_sheet else f"Student #{ev.answer_sheet_id}",
            "question_number": ev.question.question_number if ev.question else "N/A",
            "marks_awarded": ev.marks_awarded,
            "max_marks": ev.max_marks,
            "confidence_score": ev.confidence_score,
            "is_flagged": ev.is_flagged,
            "is_reviewed": ev.is_reviewed,
            "graded_at": ev.graded_at.isoformat() if ev.graded_at else None,
        }
        for ev in recent_evals_list
    ]

    return {
        "total_exams": total_exams,
        "total_answer_sheets": total_answer_sheets,
        "total_evaluations": total_evaluations,
        "pending_reviews": pending_reviews,
        "completed_evaluations": completed_evaluations,
        "recent_exams": recent_exams_data,
        "recent_evaluations": recent_evals_data,
    }


@router.get("/exam/{exam_id}")
async def get_exam_analytics(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve real performance analytics, question breakdown, and distribution for an exam."""
    exam_res = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions),
            selectinload(Exam.answer_sheets).selectinload(AnswerSheet.evaluations)
        )
        .where(Exam.id == exam_id)
    )
    exam = exam_res.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access analytics for this examination")

    # Aggregate student evaluations
    student_scores: List[float] = []
    question_totals: Dict[str, Dict[str, float]] = {
        q.question_number: {"total_awarded": 0.0, "count": 0, "max_marks": q.max_marks}
        for q in exam.questions
    }

    for sheet in exam.answer_sheets:
        if sheet.evaluations:
            sheet_total = 0.0
            for ev in sheet.evaluations:
                sheet_total += ev.marks_awarded
                q_num = ev.question.question_number if ev.question else None
                if q_num and q_num in question_totals:
                    question_totals[q_num]["total_awarded"] += ev.marks_awarded
                    question_totals[q_num]["count"] += 1
            student_scores.append(sheet_total)

    total_evaluated = len(student_scores)
    if total_evaluated == 0:
        return {
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_code": exam.exam_code,
            "total_marks": exam.max_marks,
            "evaluated_students": 0,
            "total_answer_sheets": len(exam.answer_sheets),
            "average_marks": 0.0,
            "highest_marks": 0.0,
            "lowest_marks": 0.0,
            "pass_percentage": 0.0,
            "question_stats": [],
            "grade_distribution": {"A (>=85%)": 0, "B (70-84%)": 0, "C (55-69%)": 0, "D (40-54%)": 0, "F (<40%)": 0},
        }

    avg_marks = round(sum(student_scores) / total_evaluated, 2)
    high_marks = round(max(student_scores), 2)
    low_marks = round(min(student_scores), 2)

    pass_threshold = exam.max_marks * 0.40  # KTU 40% passing standard
    passed_count = sum(1 for s in student_scores if s >= pass_threshold)
    pass_pct = round((passed_count / total_evaluated) * 100, 1)

    # Grade distribution
    grades = {"A (>=85%)": 0, "B (70-84%)": 0, "C (55-69%)": 0, "D (40-54%)": 0, "F (<40%)": 0}
    for s in student_scores:
        pct = (s / exam.max_marks) * 100 if exam.max_marks > 0 else 0
        if pct >= 85:
            grades["A (>=85%)"] += 1
        elif pct >= 70:
            grades["B (70-84%)"] += 1
        elif pct >= 55:
            grades["C (55-69%)"] += 1
        elif pct >= 40:
            grades["D (40-54%)"] += 1
        else:
            grades["F (<40%)"] += 1

    # Question statistics
    q_stats = []
    for q_num, data in question_totals.items():
        q_avg = round(data["total_awarded"] / data["count"], 2) if data["count"] > 0 else 0.0
        q_stats.append({
            "question_number": q_num,
            "max_marks": data["max_marks"],
            "average_marks": q_avg,
            "evaluated_count": data["count"],
            "average_percentage": round((q_avg / data["max_marks"]) * 100, 1) if data["max_marks"] > 0 else 0.0
        })

    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "exam_code": exam.exam_code,
        "total_marks": exam.max_marks,
        "evaluated_students": total_evaluated,
        "total_answer_sheets": len(exam.answer_sheets),
        "average_marks": avg_marks,
        "highest_marks": high_marks,
        "lowest_marks": low_marks,
        "pass_percentage": pass_pct,
        "question_stats": q_stats,
        "grade_distribution": grades,
    }
