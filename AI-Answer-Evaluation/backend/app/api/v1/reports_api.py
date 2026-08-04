"""Report export API router."""

from fastapi import APIRouter, Response, Query

from app.services.report_generator.exporter import ReportExporter

router = APIRouter(prefix="/reports", tags=["Report Export"])


@router.get("/export")
async def export_report(
    format: str = Query(default="csv", description="csv, excel, pdf"),
):
    """Export summary report in requested format (CSV, Excel, PDF)."""
    exporter = ReportExporter()
    sample_records = [
        {"student_id": 101, "question_number": "1(a)", "marks_awarded": 8.5, "max_marks": 10.0, "confidence_score": 0.92, "status": "APPROVED"},
        {"student_id": 102, "question_number": "1(a)", "marks_awarded": 6.0, "max_marks": 10.0, "confidence_score": 0.65, "status": "FLAGGED"},
    ]

    if format.lower() == "csv":
        csv_data = exporter.generate_csv_report(sample_records)
        return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=ktu_evaluation_report.csv"})
    elif format.lower() == "excel":
        excel_bytes = exporter.generate_excel_report(sample_records)
        return Response(content=excel_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=ktu_evaluation_report.xlsx"})
    elif format.lower() == "pdf":
        pdf_bytes = exporter.generate_pdf_summary("KTU Evaluation Class Summary", {"Total Students": 2, "Average Marks": 7.25, "Pass Rate": "100%"})
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=ktu_evaluation_summary.pdf"})
    else:
        return {"error": "Unsupported format. Use csv, excel, or pdf."}
