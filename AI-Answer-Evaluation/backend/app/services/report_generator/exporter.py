"""Report Export Engine generating CSV, Excel, and PDF reports."""

import csv
import io
from typing import Any, Dict, List


class ReportExporter:
    """Report Generation service for CSV, Excel, and PDF exports."""

    def generate_csv_report(self, records: List[Dict[str, Any]]) -> str:
        """Generate CSV string for student evaluations."""
        if not records:
            return "student_id,question_number,marks_awarded,max_marks,confidence_score,status\n"

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue()

    def generate_excel_report(self, records: List[Dict[str, Any]]) -> bytes:
        """Generate Excel file bytes using openpyxl or fallback CSV bytes."""
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Evaluation Report"

            if records:
                ws.append(list(records[0].keys()))
                for row in records:
                    ws.append(list(row.values()))

            stream = io.BytesIO()
            wb.save(stream)
            return stream.getvalue()
        except ImportError:
            return self.generate_csv_report(records).encode("utf-8")

    def generate_pdf_summary(self, title: str, summary_data: Dict[str, Any]) -> bytes:
        """Generate PDF report using ReportLab or HTML string bytes."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            p.drawString(100, 750, f"KTU AI Evaluation Report: {title}")
            y = 700
            for key, val in summary_data.items():
                p.drawString(100, y, f"{key}: {val}")
                y -= 25
            p.showPage()
            p.save()
            return buffer.getvalue()
        except ImportError:
            content = f"--- {title} ---\n\n" + "\n".join(f"{k}: {v}" for k, v in summary_data.items())
            return content.encode("utf-8")
