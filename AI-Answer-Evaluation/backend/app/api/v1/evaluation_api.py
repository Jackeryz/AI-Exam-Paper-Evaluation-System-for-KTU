"""Evaluation API router executing full evaluation pipeline and persisting results."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.exam import Exam, Question, ApprovedReferenceAnswer
from app.models.evaluation import AnswerSheet, ExtractedAnswer, Evaluation
from app.models.user import User, UserRole
from app.core.security import get_current_user
from app.schemas.evaluation import EvaluationResponse, CriterionDeductionResponse
from app.services.ocr_refinement.refinement_engine import OCRRefinementEngine
from app.services.grading import EvaluatorOrchestrator, GradingResult

router = APIRouter(prefix="/evaluations", tags=["AI Grading Pipeline"])


class EvaluationRequest(BaseModel):
    exam_id: int
    question_number: str
    question_text: str
    raw_student_ocr_text: str
    answer_key_text: Optional[str] = "Standard KTU Model Answer"
    rubric_text: Optional[str] = "Definition: 2 marks, Advantages: 3 marks, Applications: 5 marks"
    max_marks: float = 10.0
    ocr_confidence: float = 0.88


def format_rubric_string(rubric_json: dict) -> str:
    """Format dictionary {'Definition': 2.0, 'Analysis': 3.0} to 'Definition: 2 marks, Analysis: 3 marks'."""
    if not rubric_json:
        return "Content & Principles: 5 marks, Explanations: 5 marks"
    return ", ".join(f"{k}: {v} marks" for k, v in rubric_json.items())


@router.post("/sheet/{sheet_id}/run", response_model=List[EvaluationResponse])
async def evaluate_answer_sheet(
    sheet_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate all extracted answers for a student answer sheet against approved rubrics."""
    res = await db.execute(
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.exam).selectinload(Exam.questions).selectinload(Question.approved_reference),
            selectinload(AnswerSheet.exam).selectinload(Exam.questions).selectinload(Question.rubric),
            selectinload(AnswerSheet.exam).selectinload(Exam.questions).selectinload(Question.answer_key),
            selectinload(AnswerSheet.extracted_answers),
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.evaluations),
        )
        .where(AnswerSheet.id == sheet_id)
    )
    sheet = res.scalars().first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found.")

    if current_user.role != UserRole.ADMIN and sheet.exam and sheet.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to evaluate this answer sheet")

    if not sheet.extracted_answers:
        raise HTTPException(
            status_code=400,
            detail="No extracted answers found. Please process OCR on the sheet first."
        )

    sheet.status = "EVALUATING"
    await db.commit()

    orchestrator = EvaluatorOrchestrator()
    refinement_engine = OCRRefinementEngine()

    questions_map = {q.id: q for q in sheet.exam.questions} if sheet.exam else {}
    questions_by_num = {q.question_number.lower(): q for q in sheet.exam.questions} if sheet.exam else {}

    sheet_evaluations: List[Evaluation] = []
    has_flagged_answer = False

    for ea in sheet.extracted_answers:
        # Resolve target question strictly
        target_q = questions_map.get(ea.question_id) if ea.question_id else questions_by_num.get(ea.question_number.lower())
        if not target_q and sheet.exam and len(sheet.exam.questions) == 1:
            # Safe single-question examination fallback
            target_q = sheet.exam.questions[0]

        if not target_q:
            # Unmapped question segment: do not falsely grade against an arbitrary question
            has_flagged_answer = True
            unmapped_eval = Evaluation(
                answer_sheet_id=sheet.id,
                question_id=sheet.exam.questions[0].id if (sheet.exam and sheet.exam.questions) else 1,
                student_answer_text=ea.refined_text or ea.raw_ocr_text,
                ideal_answer_generated="[Unmapped Question - Awaiting Teacher Assignment]",
                marks_awarded=0.0,
                max_marks=10.0,
                feedback=f"Unrecognized question number '{ea.question_number}'. Routed for teacher review to assign correct question.",
                improvement_suggestions="Verify question number in handwritten script.",
                confidence_score=0.0,
                is_flagged=True,
                criterion_deductions_json=[],
                strengths_json=[],
                weaknesses_json=["Unmapped question number"],
                deduction_reasons_json=["Question number does not match configured exam questions"],
                overall_summary="Unmapped question number awaiting teacher review.",
                points_addressed_json=[],
                missing_points_json=["Unmapped question number"],
                contradictions_json=[],
                evaluation_method="DETERMINISTIC_UNMAPPED_QUESTION",
            )
            db.add(unmapped_eval)
            sheet_evaluations.append(unmapped_eval)
            continue

        q_number = target_q.question_number
        q_text = target_q.text
        q_max_marks = target_q.max_marks

        # Verify reference answer approval (cannot silently substitute unapproved answer)
        if target_q.approved_reference:
            ideal_ans = target_q.approved_reference.approved_answer
            rubric_str = format_rubric_string(target_q.approved_reference.approved_rubric_json)
        elif target_q.answer_key and (target_q.answer_key.model_answer or target_q.answer_key.ideal_solution):
            ideal_ans = target_q.answer_key.model_answer or target_q.answer_key.ideal_solution
            rubric_str = format_rubric_string(target_q.rubric.criteria_json if target_q.rubric else {})
        else:
            # Question has neither an approved reference nor an official answer key
            has_flagged_answer = True
            unapproved_eval = Evaluation(
                answer_sheet_id=sheet.id,
                question_id=target_q.id,
                student_answer_text=ea.refined_text or ea.raw_ocr_text,
                ideal_answer_generated="[No Approved Reference Answer Configured]",
                marks_awarded=0.0,
                max_marks=q_max_marks,
                feedback=f"No approved reference answer or official answer key found for Question {q_number}. Evaluation suspended and routed for teacher review.",
                improvement_suggestions="Teacher must approve an ideal answer before AI evaluation can proceed.",
                confidence_score=0.0,
                is_flagged=True,
                criterion_deductions_json=[],
                strengths_json=[],
                weaknesses_json=["Missing reference answer"],
                deduction_reasons_json=["Evaluation requires teacher-approved reference answer"],
                overall_summary="Missing reference answer. Routed for teacher review.",
                points_addressed_json=[],
                missing_points_json=["Missing approved reference answer"],
                contradictions_json=[],
                evaluation_method="DETERMINISTIC_UNAPPROVED_RUBRIC",
            )
            db.add(unapproved_eval)
            sheet_evaluations.append(unapproved_eval)
            continue

        # Use teacher-approved corrected text when present, otherwise refined text, fallback to raw OCR
        student_ans = ea.corrected_text or ea.refined_text or ea.raw_ocr_text

        # Calculate OCR confidence
        ocr_conf = sheet.ocr_result.confidence if sheet.ocr_result else 0.85

        # Run deterministic evaluation
        grading_res = await orchestrator.evaluate(
            question_number=q_number,
            question_text=q_text,
            student_answer=student_ans,
            ideal_answer=ideal_ans,
            rubric_data=rubric_str,
            ocr_confidence=ocr_conf,
            max_marks=q_max_marks,
        )

        awarded_clamped = max(0.0, min(q_max_marks, grading_res.marks_awarded))
        is_flagged = grading_res.confidence_score < 0.70 or grading_res.is_flagged
        if is_flagged:
            has_flagged_answer = True

        # Check existing evaluation for this answer sheet & question
        existing_eval = next(
            (e for e in sheet.evaluations if e.question_id == (target_q.id if target_q else 1)),
            None
        )

        criterion_deductions_data = [
            {
                "criterion": cd.criterion,
                "allocated_marks": cd.allocated_marks,
                "awarded_marks": cd.awarded_marks,
                "deducted_marks": cd.deducted_marks,
                "reason": cd.reason,
            }
            for cd in grading_res.score_breakdown.criterion_deductions
        ]

        fb = grading_res.feedback
        if hasattr(fb, "overall_summary"):
            fb_summary = fb.overall_summary or "Evaluation completed."
            fb_suggestions = "; ".join(getattr(fb, "improvement_suggestions", []))
            fb_strengths = getattr(fb, "strengths", [])
            fb_weaknesses = getattr(fb, "weaknesses", [])
            fb_reasons = getattr(fb, "reasons_for_deduction", [])
        elif isinstance(fb, dict):
            fb_summary = fb.get("overall_summary", str(fb))
            fb_suggestions = "; ".join(fb.get("improvement_suggestions", []))
            fb_strengths = fb.get("strengths", [])
            fb_weaknesses = fb.get("weaknesses", [])
            fb_reasons = fb.get("reasons_for_deduction", [])
        else:
            fb_summary = str(fb)
            fb_suggestions = "Practice technical terms and detailed diagrams."
            fb_strengths = []
            fb_weaknesses = []
            fb_reasons = []

        if existing_eval:
            existing_eval.student_answer_text = student_ans
            existing_eval.ideal_answer_generated = ideal_ans
            # Preserve teacher marks if already reviewed and overridden
            if not existing_eval.is_reviewed:
                existing_eval.marks_awarded = awarded_clamped
                existing_eval.feedback = fb_summary
                existing_eval.is_flagged = is_flagged
            existing_eval.max_marks = q_max_marks
            existing_eval.improvement_suggestions = fb_suggestions
            existing_eval.confidence_score = grading_res.confidence_score
            existing_eval.criterion_deductions_json = criterion_deductions_data
            existing_eval.strengths_json = fb_strengths
            existing_eval.weaknesses_json = fb_weaknesses
            existing_eval.deduction_reasons_json = fb_reasons
            existing_eval.overall_summary = fb_summary
            existing_eval.points_addressed_json = grading_res.points_addressed
            existing_eval.missing_points_json = grading_res.missing_points
            existing_eval.contradictions_json = grading_res.identified_contradictions
            existing_eval.evaluation_method = grading_res.evaluation_method
            eval_record = existing_eval
        else:
            eval_record = Evaluation(
                answer_sheet_id=sheet.id,
                question_id=target_q.id if target_q else 1,
                student_answer_text=student_ans,
                ideal_answer_generated=ideal_ans,
                marks_awarded=awarded_clamped,
                max_marks=q_max_marks,
                feedback=fb_summary,
                improvement_suggestions=fb_suggestions,
                confidence_score=grading_res.confidence_score,
                is_flagged=is_flagged,
                criterion_deductions_json=criterion_deductions_data,
                strengths_json=fb_strengths,
                weaknesses_json=fb_weaknesses,
                deduction_reasons_json=fb_reasons,
                overall_summary=fb_summary,
                points_addressed_json=grading_res.points_addressed,
                missing_points_json=grading_res.missing_points,
                contradictions_json=grading_res.identified_contradictions,
                evaluation_method=grading_res.evaluation_method,
            )
            db.add(eval_record)

        sheet_evaluations.append(eval_record)

    any_unreviewed_flagged = any(e.is_flagged and not e.is_reviewed for e in sheet_evaluations)
    all_reviewed = all(e.is_reviewed for e in sheet_evaluations)
    if all_reviewed:
        sheet.status = "REVIEWED"
    elif any_unreviewed_flagged:
        sheet.status = "AWAITING_REVIEW"
    else:
        sheet.status = "EVALUATED"
    await db.commit()

    # Re-fetch evaluations with responses
    res = await db.execute(
        select(Evaluation)
        .options(selectinload(Evaluation.question))
        .where(Evaluation.answer_sheet_id == sheet_id)
    )
    all_evals = res.scalars().all()

    output = []
    for ev in all_evals:
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
                student_identifier=sheet.student_identifier,
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


@router.get("/sheet/{sheet_id}", response_model=List[EvaluationResponse])
async def get_sheet_evaluations(sheet_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve all evaluation records for an answer sheet."""
    sheet_res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
    sheet = sheet_res.scalars().first()

    res = await db.execute(
        select(Evaluation)
        .options(selectinload(Evaluation.question))
        .where(Evaluation.answer_sheet_id == sheet_id)
    )
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
                student_identifier=sheet.student_identifier if sheet else None,
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


@router.get("/{eval_id}", response_model=EvaluationResponse)
async def get_evaluation(
    eval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed evaluation record with criterion deductions."""
    res = await db.execute(
        select(Evaluation)
        .options(
            selectinload(Evaluation.question),
            selectinload(Evaluation.answer_sheet).selectinload(AnswerSheet.exam),
        )
        .where(Evaluation.id == eval_id)
    )
    ev = res.scalars().first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation record not found.")

    exam_teacher = ev.answer_sheet.exam.teacher_id if (ev.answer_sheet and ev.answer_sheet.exam) else None
    if current_user.role != UserRole.ADMIN and exam_teacher != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this evaluation")

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


@router.post("/evaluate", response_model=GradingResult)
async def run_single_evaluation(
    request: EvaluationRequest,
    current_user: User = Depends(get_current_user),
):
    """Direct evaluation for quick ad-hoc testing."""
    orchestrator = EvaluatorOrchestrator()
    result = await orchestrator.evaluate(
        question_number=request.question_number,
        question_text=request.question_text,
        student_answer=request.raw_student_ocr_text,
        ideal_answer=request.answer_key_text,
        rubric_data=request.rubric_text,
        ocr_confidence=request.ocr_confidence,
        max_marks=request.max_marks,
    )
    return result
