"""Benchmark orchestration and comparison report generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psutil
from PIL import Image

from .models import OCRResult
from .router import OCRRouter


@dataclass(slots=True)
class BenchmarkRecord:
    """Comparison data for one routed page."""

    input_filename: str
    paddle: OCRResult
    qwen: OCRResult | None
    routed: OCRResult
    memory_mb: float
    ground_truth_accuracy: float | None

    def to_dict(self) -> dict:
        """Serialize the benchmark record."""
        return {
            "input_filename": self.input_filename,
            "paddle": self.paddle.to_dict(),
            "qwen": self.qwen.to_dict() if self.qwen else None,
            "routed": self.routed.to_dict(),
            "memory_mb": self.memory_mb,
            "ground_truth_accuracy": self.ground_truth_accuracy,
        }


def character_accuracy(transcription: str, ground_truth: str) -> float:
    """Calculate normalized character-position accuracy for available truth text."""
    expected = " ".join(ground_truth.split())
    actual = " ".join(transcription.split())
    if not expected:
        return 0.0
    matches = sum(left == right for left, right in zip(actual, expected))
    return round(matches / max(len(actual), len(expected)), 4)


class BenchmarkRunner:
    """Run both strategies through the router and persist comparison artifacts."""

    def __init__(self, router: OCRRouter, ground_truth_dir: Path | None = None) -> None:
        self.router = router
        self.ground_truth_dir = ground_truth_dir
        self.records: list[BenchmarkRecord] = []

    def process_page(
        self, image: Image.Image, page_number: int, input_filename: str
    ) -> BenchmarkRecord:
        """Benchmark a page; the router's benchmark mode forces both engines."""
        self.router.benchmark_mode = True
        memory_before = psutil.Process().memory_info().rss
        routed = self.router.process(
            image, page_number=page_number, input_filename=input_filename
        )
        paddle = self.router.last_paddle_result
        qwen = self.router.last_qwen_result
        if paddle is None:
            raise RuntimeError("PaddleOCR did not return a benchmark result")
        memory_mb = round(
            (psutil.Process().memory_info().rss - memory_before) / (1024 * 1024), 3
        )
        accuracy = self._ground_truth_accuracy(input_filename, routed.text)
        record = BenchmarkRecord(
            input_filename=input_filename,
            paddle=paddle,
            qwen=qwen,
            routed=routed,
            memory_mb=memory_mb,
            ground_truth_accuracy=accuracy,
        )
        self.records.append(record)
        return record

    def write_reports(self) -> tuple[Path, Path]:
        """Write machine-readable comparison data and a compact Markdown summary."""
        output_root = self.router.output_root
        output_root.mkdir(parents=True, exist_ok=True)
        comparison_path = output_root / "comparison.json"
        summary_path = output_root / "summary.md"
        comparison_path.write_text(
            json.dumps([record.to_dict() for record in self.records], indent=2),
            encoding="utf-8",
        )
        total = len(self.records)
        paddle_only = sum(record.routed.engine_used == "paddleocr" for record in self.records)
        qwen_required = total - paddle_only
        paddle_confidences = [
            record.paddle.confidence
            for record in self.records
            if record.paddle.confidence is not None
        ]
        accuracies = [
            record.ground_truth_accuracy
            for record in self.records
            if record.ground_truth_accuracy is not None
        ]
        average = lambda values: round(sum(values) / len(values), 4) if values else None
        summary_path.write_text(
            "# Adaptive OCR Benchmark Summary\n\n"
            f"- Documents handled only by PaddleOCR: {paddle_only}\n"
            f"- Documents requiring Qwen2.5-VL: {qwen_required}\n"
            f"- Average Paddle confidence: {average(paddle_confidences)}\n"
            f"- Average routed latency (seconds): {average([record.routed.processing_time for record in self.records])}\n"
            f"- Average OCR accuracy: {average(accuracies)}\n",
            encoding="utf-8",
        )
        return comparison_path, summary_path

    def _ground_truth_accuracy(self, input_filename: str, transcription: str) -> float | None:
        if self.ground_truth_dir is None:
            return None
        ground_truth_path = self.ground_truth_dir / f"{Path(input_filename).stem}.txt"
        if not ground_truth_path.exists():
            return None
        return character_accuracy(transcription, ground_truth_path.read_text(encoding="utf-8"))
