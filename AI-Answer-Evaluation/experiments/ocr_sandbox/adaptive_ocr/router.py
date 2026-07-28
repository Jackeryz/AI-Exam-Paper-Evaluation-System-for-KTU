"""Confidence-based OCR routing and structured document logging."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from PIL import Image

from experiments.ocr_sandbox.utils import config

from .classification import PageStyleClassifier
from .engines import BaseOCR, PaddleOCRStrategy, QwenOCRStrategy
from .models import OCRResult
from .preprocessing import OpenCVPreprocessor


def build_router_logger(output_root: Path) -> logging.Logger:
    """Create a sandbox-local logger without duplicating handlers."""
    logger = logging.getLogger("ocr_sandbox.router")
    logger.setLevel(logging.INFO)
    log_path = output_root / "routed" / config.ROUTER_LOG_FILENAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_path
        for handler in logger.handlers
    ):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


class OCRRouter:
    """Route a preprocessed page to Qwen only when Paddle confidence is low."""

    def __init__(
        self,
        paddle: BaseOCR | None = None,
        qwen: BaseOCR | None = None,
        *,
        confidence_threshold: float = config.OCR_CONFIDENCE_THRESHOLD,
        benchmark_mode: bool = config.BENCHMARK_MODE,
        preprocessor: OpenCVPreprocessor | None = None,
        classifier: PageStyleClassifier | None = None,
        output_root: Path | None = None,
    ) -> None:
        """Build a router with injectable strategies for tests and future services."""
        self.paddle = paddle or PaddleOCRStrategy()
        self.qwen = qwen or QwenOCRStrategy()
        self.confidence_threshold = confidence_threshold
        self.benchmark_mode = benchmark_mode
        self.preprocessor = preprocessor or OpenCVPreprocessor()
        self.classifier = classifier or PageStyleClassifier()
        sandbox_root = Path(__file__).resolve().parents[1]
        self.output_root = output_root or sandbox_root / config.ADAPTIVE_OUTPUT_DIR
        for output_name in ("paddle", "qwen", "routed"):
            (self.output_root / output_name).mkdir(parents=True, exist_ok=True)
        self.logger = build_router_logger(self.output_root)
        self.last_paddle_result: OCRResult | None = None
        self.last_qwen_result: OCRResult | None = None

    def process(
        self,
        image: Image.Image,
        *,
        page_number: int = 1,
        input_filename: str = "",
    ) -> OCRResult:
        """Process one page and return Paddle or Qwen according to confidence."""
        started_at = perf_counter()
        self.last_paddle_result = None
        self.last_qwen_result = None
        prepared_image = self.preprocessor.process(image)
        classification = (
            self.classifier.classify(prepared_image)
            if config.ENABLE_IMAGE_CLASSIFICATION
            else None
        )
        paddle_result = self.paddle.process(prepared_image, page_number)
        paddle_result.page_classification = classification
        self.last_paddle_result = paddle_result
        fallback_required = (
            paddle_result.confidence is None
            or paddle_result.confidence < self.confidence_threshold
        )
        qwen_result: OCRResult | None = None
        if fallback_required or self.benchmark_mode:
            qwen_result = self.qwen.process(prepared_image, page_number)
            qwen_result.page_classification = classification
            self.last_qwen_result = qwen_result

        winning_result = qwen_result if fallback_required else paddle_result
        assert winning_result is not None
        final_result = replace(
            winning_result, processing_time=perf_counter() - started_at
        )
        self.logger.info(
            "input=%s page=%s paddle_confidence=%s threshold=%s fallback=%s "
            "final_engine=%s processing_time=%.3f classification=%s",
            input_filename,
            page_number,
            paddle_result.confidence,
            self.confidence_threshold,
            fallback_required,
            final_result.engine_used,
            final_result.processing_time,
            classification,
        )
        return final_result
