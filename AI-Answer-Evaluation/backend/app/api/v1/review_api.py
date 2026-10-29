"""Teacher Review & Override API v1 router with database persistence and audit trails."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.evaluation import Evaluation, Feedback, AnswerSheet
from app.models.exam import Question, Exam
from app.models.user import User, UserRole
from app.core.security import get_current_user
from app.schemas.evaluation import EvaluationResponse, CriterionDeductionResponse

router = APIRouter(prefix="/reviews", tags=["Teacher Review"])


class TeacherOverrideRequest(BaseModel):
    evaluation_id: Optional[int] = None
    teacher_id: Optional[int] = None
    teacher_marks: float
    teacher_feedback: Optional[str] = None
    comments: Optional[str] = None
    approve: bool = True


@router.get("/pending", response_model=List[EvaluationResponse])
async def get_pending_reviews(
    exam_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all flagged evaluations awaiting teacher review."""
    stmt = (
        select(Evaluation)
        .options(
            selectinload(Evaluation.question),
            selectinload(Evaluation.answer_sheet).selectinload(AnswerSheet.exam),
        )
        .join(AnswerSheet, Evaluation.answer_sheet_id == AnswerSheet.id)
        .where(Evaluation.is_flagged == True, Evaluation.is_reviewed == False)
    )

    if exam_id:
        stmt = stmt.where(AnswerSheet.exam_id == exam_id)

    if current_user.role != UserRole.ADMIN:
        stmt = stmt.join(Exam, AnswerSheet.exam_id == Exam.id).where(Exam.teacher_id == current_user.id)

    res = await db.execute(stmt)
    evals = res.scalars().all()

    output = []
    for ev in evals:
        deductions = [
            CriterionDeductionResponse(
                criterion=d.get("criterion", "General"),
                allocated_marks=d.get("allocated_marks", 0.0),
                awarded_marks=d.get("awarded_marks", 0.0),
                deducted_marks=d.get("deducted_marks", 0.0),
                reason=d.get("reason", "Mark deduction applied"),
                evidence=d.get("evidence"),
            )
            for d in (ev.criterion_deductions_json or [])
        ]
        output.append(
            EvaluationResponse(
                id=ev.id,
                answer_sheet_id=ev.answer_sheet_id,
                question_id=ev.question_id,
                student_identifier=ev.answer_sheet.student_identifier if ev.answer_sheet else None,
                question_number=ev.question.question_number if ev.question else "N/A",
                student_answer_text=ev.student_answer_text,
                ideal_answer_generated=ev.ideal_answer_generated,
                marks_awarded=ev.marks_awarded,
                max_marks=ev.max_marks,
                feedback=ev.feedback,
                improvement_suggestions=ev.improvement_suggestions,
                confidence_score=ev.confidence_score,
                is_flagged=ev.is_flagged,
                is_reviewed=ev.is_reviewed,
                criterion_deductions=deductions,
                strengths=ev.strengths_json or [],
                weaknesses=ev.weaknesses_json or [],
                reasons_for_deduction=ev.deduction_reasons_json or [],
                overall_summary=ev.overall_summary,
                points_addressed=ev.points_addressed_json or [],
                missing_points=ev.missing_points_json or [],
                identified_contradictions=ev.contradictions_json or [],
                evaluation_method=ev.evaluation_method or "DETERMINISTIC_HEURISTIC_FALLBACK",
                graded_at=ev.graded_at,
            )
        )
    return output


@router.post("/override", response_model=EvaluationResponse)
@router.post("/evaluations/{eval_id}/override", response_model=EvaluationResponse)
async def submit_teacher_override(
    request: TeacherOverrideRequest,
    eval_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit teacher manual score/feedback override with full audit trail."""
    target_id = eval_id or request.evaluation_id
    if not target_id:
        raise HTTPException(status_code=400, detail="evaluation_id must be provided.")

    res = await db.execute(
        select(Evaluation)
        .options(
            selectinload(Evaluation.question),
            selectinload(Evaluation.answer_sheet).selectinload(AnswerSheet.exam),
            selectinload(Evaluation.teacher_feedback),
        )
        .where(Evaluation.id == target_id)
    )
    ev = res.scalars().first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation record not found.")

    exam_teacher = ev.answer_sheet.exam.teacher_id if (ev.answer_sheet and ev.answer_sheet.exam) else None
    if current_user.role != UserRole.ADMIN and exam_teacher != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to override evaluations for this examination")

    if request.teacher_marks < 0.0 or request.teacher_marks > ev.max_marks:
        raise HTTPException(
            status_code=400,
            detail=f"Override marks ({request.teacher_marks}) must be between 0.0 and question maximum marks ({ev.max_marks})."
        )

    orig_marks = ev.marks_awarded
    orig_fb = ev.feedback

    # Update Evaluation
    ev.marks_awarded = request.teacher_marks
    if request.teacher_feedback:
        ev.feedback = request.teacher_feedback
    ev.is_reviewed = True
    ev.is_flagged = False

    # Create or update Feedback record for audit trail - strictly using current_user.id
    if ev.teacher_feedback:
        ev.teacher_feedback.teacher_id = current_user.id
        ev.teacher_feedback.teacher_marks = request.teacher_marks
        ev.teacher_feedback.teacher_feedback = request.teacher_feedback or orig_fb
        ev.teacher_feedback.comments = request.comments
    else:
        audit = Feedback(
            evaluation_id=ev.id,
            teacher_id=current_user.id,
            original_marks=orig_marks,
            teacher_marks=request.teacher_marks,
            original_feedback=orig_fb,
            teacher_feedback=request.teacher_feedback or orig_fb,
            comments=request.comments,
        )
        db.add(audit)

    # Update sheet status to REVIEWED if all evaluations for the sheet are reviewed
    if ev.answer_sheet:
        all_evals_res = await db.execute(
            select(Evaluation).where(Evaluation.answer_sheet_id == ev.answer_sheet_id)
        )
        all_evals = all_evals_res.scalars().all()
        if all(e.is_reviewed for e in all_evals):
            ev.answer_sheet.status = "REVIEWED"

    await db.commit()
    await db.refresh(ev)

    deductions = [
        CriterionDeductionResponse(
            criterion=d.get("criterion", "General"),
            allocated_marks=d.get("allocated_marks", 0.0),
            awarded_marks=d.get("awarded_marks", 0.0),
            deducted_marks=d.get("deducted_marks", 0.0),
            reason=d.get("reason", "Mark deduction applied"),
            evidence=d.get("evidence"),
        )
        for d in (ev.criterion_deductions_json or [])
    ]

    return EvaluationResponse(
        id=ev.id,
        answer_sheet_id=ev.answer_sheet_id,
        question_id=ev.question_id,
        student_identifier=ev.answer_sheet.student_identifier if ev.answer_sheet else None,
        question_number=ev.question.question_number if ev.question else "N/A",
        student_answer_text=ev.student_answer_text,
        ideal_answer_generated=ev.ideal_answer_generated,
        marks_awarded=ev.marks_awarded,
        max_marks=ev.max_marks,
        feedback=ev.feedback,
        improvement_suggestions=ev.improvement_suggestions,
        confidence_score=ev.confidence_score,
        is_flagged=ev.is_flagged,
        is_reviewed=ev.is_reviewed,
        criterion_deductions=deductions,
        strengths=ev.strengths_json or [],
        weaknesses=ev.weaknesses_json or [],
        reasons_for_deduction=ev.deduction_reasons_json or [],
        overall_summary=ev.overall_summary,
        points_addressed=ev.points_addressed_json or [],
        missing_points=ev.missing_points_json or [],
        identified_contradictions=ev.contradictions_json or [],
        evaluation_method=ev.evaluation_method or "DETERMINISTIC_HEURISTIC_FALLBACK",
        graded_at=ev.graded_at,
    )
