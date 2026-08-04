"""Analytics API v1 router."""

from fastapi import APIRouter
from app.services.analytics.analytics_engine import AnalyticsEngine, AnalyticsSummary

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/exam/{exam_id}", response_model=AnalyticsSummary)
async def get_exam_analytics(exam_id: int):
    """Retrieve performance analytics, weak topics, and difficulty distribution for an exam."""
    engine = AnalyticsEngine()
    mock_data = [
        {"student_id": 1, "total_marks": 78.5},
        {"student_id": 2, "total_marks": 64.0},
        {"student_id": 3, "total_marks": 82.0},
        {"student_id": 4, "total_marks": 45.5},
    ]
    return engine.compute_exam_analytics(exam_id=exam_id, student_evaluations=mock_data)
