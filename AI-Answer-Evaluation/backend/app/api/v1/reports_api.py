"""Report export API router for examination-level result summaries and CSV/Excel/PDF exports."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.exam import Exam, Question
from app.models.evaluation import AnswerSheet, Evaluation, Feedback
from app.models.user import User, UserRole
from app.core.security import get_current_user
from app.services.report_generator.exporter import ReportExporter

router = APIRouter(prefix="/reports", tags=["Report Export"])


@router.get("/exam/{exam_id}/summary")
async def get_exam_summary_report(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full structured result matrix for all students in an exam."""
    exam_res = await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.questions),
            selectinload(Exam.answer_sheets)
            .selectinload(AnswerSheet.evaluations)
            .selectinload(Evaluation.teacher_feedback),
            selectinload(Exam.answer_sheets)
            .selectinload(AnswerSheet.evaluations)
            .selectinload(Evaluation.question)
        )
        .where(Exam.id == exam_id)
    )
    exam = exam_res.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access reports for this examination")

    questions_info = [
        {"id": q.id, "question_number": q.question_number, "max_marks": q.max_marks}
        for q in sorted(exam.questions, key=lambda x: x.question_number)
    ]

    students_data = []
    for sheet in exam.answer_sheets:
        q_scores: Dict[str, float] = {}
        total_awarded = 0.0
        confidences = []
        is_sheet_flagged = False
        is_sheet_reviewed = True
        has_any_override = False

        for ev in sheet.evaluations:
            q_num = ev.question.question_number if ev.question else f"Q{ev.question_id}"
            
            # If teacher provided an override, use the overridden score
            if ev.teacher_feedback:
                awarded = ev.teacher_feedback.teacher_marks
                has_any_override = True
            else:
                awarded = ev.marks_awarded
            
            q_scores[q_num] = round(awarded, 2)
            total_awarded += awarded
            confidences.append(ev.confidence_score)
            if ev.is_flagged and not ev.is_reviewed:
                is_sheet_flagged = True
            if not ev.is_reviewed:
                is_sheet_reviewed = False

        avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        pct = round((total_awarded / exam.max_marks) * 100, 1) if exam.max_marks > 0 else 0.0

        students_data.append({
            "sheet_id": sheet.id,
            "student_identifier": sheet.student_identifier or f"Student #{sheet.id}",
            "original_filename": sheet.original_filename,
            "status": sheet.status,
            "question_scores": q_scores,
            "total_awarded": round(total_awarded, 2),
            "max_marks": exam.max_marks,
            "percentage": pct,
            "average_confidence": avg_conf,
            "is_flagged": is_sheet_flagged,
            "is_reviewed": is_sheet_reviewed,
            "has_override": has_any_override,
        })

    # Sort students by student_identifier
    students_data.sort(key=lambda s: s["student_identifier"])

    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "course_code": exam.subject_code or "",
        "exam_code": exam.exam_code,
        "total_marks": exam.max_marks,
        "questions": questions_info,
        "students": students_data,
    }


@router.get("/exam/{exam_id}/export")
async def export_exam_report(
    exam_id: int,
    format: str = Query(default="csv", description="csv, excel, pdf"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export complete exam evaluation results to CSV, Excel, or PDF."""
    summary_data = await get_exam_summary_report(exam_id=exam_id, current_user=current_user, db=db)
    exporter = ReportExporter()

    questions = summary_data["questions"]
    students = summary_data["students"]
    exam_code = summary_data["exam_code"] or f"EXAM_{exam_id}"

    # Flatten into tabular records
    records: List[Dict[str, Any]] = []
    for s in students:
        row: Dict[str, Any] = {
            "Student Roll / Identifier": s["student_identifier"],
            "Answer Sheet ID": s["sheet_id"],
        }
        # Add marks for each configured question
        for q in questions:
            q_num = q["question_number"]
            row[f"Q {q_num} ({q['max_marks']}m)"] = s["question_scores"].get(q_num, 0.0)

        row["Total Marks Awarded"] = s["total_awarded"]
        row["Max Marks"] = summary_data["total_marks"]
        row["Percentage (%)"] = s["percentage"]
        row["Confidence Score"] = s["average_confidence"]
        row["Status"] = s["status"]
        row["Teacher Overridden"] = "YES" if s["has_override"] else "NO"
        records.append(row)

    fmt = format.lower()
    if fmt == "csv":
        csv_data = exporter.generate_csv_report(records)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=KTU_{exam_code}_Results.csv"}
        )
    elif fmt == "excel":
        excel_bytes = exporter.generate_excel_report(records)
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=KTU_{exam_code}_Results.xlsx"}
        )
    elif fmt == "pdf":
        avg_marks = round(sum(s["total_awarded"] for s in students) / len(students), 2) if students else 0.0
        pdf_summary = {
            "Course": f"{summary_data['course_code']} - {summary_data['exam_title']}",
            "Exam Code": exam_code,
            "Total Students": len(students),
            "Max Marks": summary_data["total_marks"],
            "Class Average Marks": avg_marks,
            "Pass Rate": f"{round((sum(1 for s in students if s['percentage'] >= 40) / len(students)) * 100, 1) if students else 0.0}%",
        }
        pdf_bytes = exporter.generate_pdf_summary(f"KTU Evaluation Report ({exam_code})", pdf_summary)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=KTU_{exam_code}_Summary.pdf"}
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use csv, excel, or pdf.")


@router.get("/export")
async def export_general_report(
    format: str = Query(default="csv", description="csv, excel, pdf"),
):
    """Fallback export endpoint for general queries."""
    exporter = ReportExporter()
    sample_records = [
        {"student_id": 101, "question_number": "1(a)", "marks_awarded": 8.5, "max_marks": 10.0, "confidence_score": 0.92, "status": "APPROVED"},
    ]
    if format.lower() == "csv":
        csv_data = exporter.generate_csv_report(sample_records)
        return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=ktu_evaluation_report.csv"})
    elif format.lower() == "excel":
        excel_bytes = exporter.generate_excel_report(sample_records)
        return Response(content=excel_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=ktu_evaluation_report.xlsx"})
    return {"status": "ok"}
