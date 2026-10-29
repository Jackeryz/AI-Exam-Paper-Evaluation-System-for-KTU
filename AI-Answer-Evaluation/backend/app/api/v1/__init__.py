"""API v1 Package."""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.exams import router as exams_router
from app.api.v1.answer_sheets_api import router as answer_sheets_router
from app.api.v1.reference_answers import router as reference_answers_router
from app.api.v1.ocr_api import router as ocr_router
from app.api.v1.evaluation_api import router as evaluation_router
from app.api.v1.review_api import router as review_router
from app.api.v1.analytics_api import router as analytics_router
from app.api.v1.reports_api import router as reports_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(exams_router)
api_v1_router.include_router(answer_sheets_router)
api_v1_router.include_router(reference_answers_router)
api_v1_router.include_router(ocr_router)
api_v1_router.include_router(evaluation_router)
api_v1_router.include_router(review_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(reports_router)

__all__ = ["api_v1_router"]
