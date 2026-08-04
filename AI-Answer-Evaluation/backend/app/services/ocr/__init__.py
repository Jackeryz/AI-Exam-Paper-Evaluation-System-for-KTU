"""OCR service package."""

from app.services.ocr.ocr_interface import (
    OCRInterface,
    PaddleOCRService,
    TrOCRService,
    EasyOCRService,
    GoogleVisionService,
    MistralOCRService,
    OCRResultData,
    get_ocr_service,
)

__all__ = [
    "OCRInterface",
    "PaddleOCRService",
    "TrOCRService",
    "EasyOCRService",
    "GoogleVisionService",
    "MistralOCRService",
    "OCRResultData",
    "get_ocr_service",
]
