"""OCR Interface and provider implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import logger


class BoundingBox(BaseModel):
    """Bounding box coordinates for detected text."""
    text: str
    confidence: float
    bbox: List[List[int]]


class OCRResultData(BaseModel):
    """Standardized OCR output contract."""
    text: str
    confidence: float
    engine: str
    page_number: int = 1
    bounding_boxes: List[BoundingBox] = Field(default_factory=list)


class OCRInterface(ABC):
    """Abstract base class for all OCR providers."""

    engine_name: str

    @abstractmethod
    def process_file(self, file_path: Path, page_number: int = 1) -> OCRResultData:
        """Process an image or PDF page and return standardized OCR data."""
        pass


class PaddleOCRService(OCRInterface):
    """PaddleOCR service wrapping the existing sandbox OCR engine."""

    engine_name = "PADDLE"

    def __init__(self) -> None:
        self._engine = None

    def _get_engine(self) -> Any:
        """Lazy load the OCR engine from the existing experiments/ocr_sandbox."""
        if self._engine is None:
            try:
                from experiments.ocr_sandbox.test_ocr import initialize_ocr
                self._engine = initialize_ocr()
            except Exception as exc:
                logger.warning(f"PaddleOCR engine load warning: {exc}. Falling back to sandbox engine.")
                raise RuntimeError(f"Unable to initialize PaddleOCR engine: {exc}") from exc
        return self._engine

    def process_file(self, file_path: Path, page_number: int = 1) -> OCRResultData:
        """Process file using sandbox PaddleOCR runner."""
        from experiments.ocr_sandbox.test_ocr import load_pages, run_ocr

        pages = load_pages(file_path)
        selected_page = next((p for p_num, p in pages if p_num == page_number), pages[0][1] if pages else None)
        
        if selected_page is None:
            raise ValueError(f"Page {page_number} not found in {file_path}")

        engine = self._get_engine()
        raw_result = run_ocr(engine, selected_page)

        bboxes = [
            BoundingBox(
                text=b.get("text", ""),
                confidence=float(b.get("confidence", 0.0)),
                bbox=b.get("bbox", [])
            )
            for b in raw_result.get("bounding_boxes", [])
        ]

        return OCRResultData(
            text=raw_result.get("text", ""),
            confidence=float(raw_result.get("confidence", 0.0)),
            engine=self.engine_name,
            page_number=page_number,
            bounding_boxes=bboxes,
        )


class TrOCRService(OCRInterface):
    """TrOCR Transformer-based OCR Service implementation stub."""
    engine_name = "TROCR"

    def process_file(self, file_path: Path, page_number: int = 1) -> OCRResultData:
        logger.info(f"Processing {file_path} with TrOCR service (mock/stub).")
        return OCRResultData(
            text=f"[TrOCR Extracted Text from {file_path.name}]",
            confidence=0.85,
            engine=self.engine_name,
            page_number=page_number,
        )


class EasyOCRService(OCRInterface):
    """EasyOCR Service implementation stub."""
    engine_name = "EASYOCR"

    def process_file(self, file_path: Path, page_number: int = 1) -> OCRResultData:
        logger.info(f"Processing {file_path} with EasyOCR service (mock/stub).")
        return OCRResultData(
            text=f"[EasyOCR Extracted Text from {file_path.name}]",
            confidence=0.82,
            engine=self.engine_name,
            page_number=page_number,
        )


class GoogleVisionService(OCRInterface):
    """Google Cloud Vision OCR Service implementation stub."""
    engine_name = "GOOGLE_VISION"

    def process_file(self, file_path: Path, page_number: int = 1) -> OCRResultData:
        logger.info(f"Processing {file_path} with Google Vision OCR service.")
        return OCRResultData(
            text=f"[Google Vision Text from {file_path.name}]",
            confidence=0.95,
            engine=self.engine_name,
            page_number=page_number,
        )


class MistralOCRService(OCRInterface):
    """Mistral OCR Service implementation stub."""
    engine_name = "MISTRAL"

    def process_file(self, file_path: Path, page_number: int = 1) -> OCRResultData:
        logger.info(f"Processing {file_path} with Mistral OCR service.")
        return OCRResultData(
            text=f"[Mistral OCR Text from {file_path.name}]",
            confidence=0.90,
            engine=self.engine_name,
            page_number=page_number,
        )


def get_ocr_service(engine_override: Optional[str] = None) -> OCRInterface:
    """Factory function returning configured OCR engine instance."""
    settings = get_settings()
    engine_name = (engine_override or settings.OCR_ENGINE).upper()

    services = {
        "PADDLE": PaddleOCRService,
        "PADDLEOCR": PaddleOCRService,
        "TROCR": TrOCRService,
        "EASYOCR": EasyOCRService,
        "GOOGLE_VISION": GoogleVisionService,
        "MISTRAL": MistralOCRService,
    }

    service_class = services.get(engine_name, PaddleOCRService)
    return service_class()
