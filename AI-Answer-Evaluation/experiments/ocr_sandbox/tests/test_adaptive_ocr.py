"""Unit tests for confidence-based adaptive OCR routing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from experiments.ocr_sandbox.adaptive_ocr.benchmark import BenchmarkRunner
from experiments.ocr_sandbox.adaptive_ocr.engines import BaseOCR
from experiments.ocr_sandbox.adaptive_ocr.models import OCRResult
from experiments.ocr_sandbox.adaptive_ocr.router import OCRRouter


class FakeOCR(BaseOCR):
    """Deterministic OCR strategy used to test router decisions."""

    def __init__(self, engine_name: str, confidence: float | None, text: str) -> None:
        self.engine_name = engine_name
        self.confidence = confidence
        self.text = text
        self.calls = 0

    def process(self, image: Image.Image, page_number: int) -> OCRResult:
        self.calls += 1
        return OCRResult(
            text=self.text,
            confidence=self.confidence,
            processing_time=0.01,
            engine_used=self.engine_name,
            page_number=page_number,
            bounding_boxes=[],
        )


class IdentityPreprocessor:
    """Avoid OpenCV work in routing unit tests."""

    def process(self, image: Image.Image) -> Image.Image:
        return image


class FixedClassifier:
    """Provide deterministic metadata without influencing routing."""

    def classify(self, image: Image.Image) -> str:
        return "PRINTED"


def build_router(tmp_path: Path, paddle_confidence: float, benchmark_mode: bool = False):
    paddle = FakeOCR("paddleocr", paddle_confidence, "paddle text")
    qwen = FakeOCR("qwen2.5-vl", None, "qwen text")
    return (
        OCRRouter(
            paddle=paddle,
            qwen=qwen,
            confidence_threshold=0.90,
            benchmark_mode=benchmark_mode,
            preprocessor=IdentityPreprocessor(),
            classifier=FixedClassifier(),
            output_root=tmp_path,
        ),
        paddle,
        qwen,
    )


def test_router_returns_paddle_when_confidence_meets_threshold(tmp_path):
    router, paddle, qwen = build_router(tmp_path, 0.90)

    result = router.process(Image.new("RGB", (8, 8)), input_filename="page.png")

    assert result.engine_used == "paddleocr"
    assert result.text == "paddle text"
    assert result.page_classification == "PRINTED"
    assert paddle.calls == 1
    assert qwen.calls == 0


def test_router_falls_back_to_qwen_below_threshold(tmp_path):
    router, paddle, qwen = build_router(tmp_path, 0.89)

    result = router.process(Image.new("RGB", (8, 8)), page_number=2)

    assert result.engine_used == "qwen2.5-vl"
    assert result.text == "qwen text"
    assert paddle.calls == 1
    assert qwen.calls == 1


def test_benchmark_runs_both_engines_and_writes_reports(tmp_path):
    router, paddle, qwen = build_router(tmp_path, 0.95, benchmark_mode=True)
    runner = BenchmarkRunner(router)

    record = runner.process_page(Image.new("RGB", (8, 8)), 1, "page.png")
    comparison_path, summary_path = runner.write_reports()

    assert record.routed.engine_used == "paddleocr"
    assert record.qwen is not None
    assert paddle.calls == 1
    assert qwen.calls == 1
    assert comparison_path.exists()
    assert "Documents handled only by PaddleOCR: 1" in summary_path.read_text(
        encoding="utf-8"
    )
