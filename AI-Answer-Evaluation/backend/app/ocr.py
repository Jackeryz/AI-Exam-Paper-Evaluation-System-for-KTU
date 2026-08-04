"""OCR Service module delegating to app.services.ocr."""

from app.services.ocr import (
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
