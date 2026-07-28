"""Persistence helpers for separate Paddle, Qwen, and routed outputs."""

from __future__ import annotations

import json
from pathlib import Path

from .models import OCRResult


def save_result(output_root: Path, result: OCRResult, input_path: Path) -> Path:
    """Save one normalized result beneath its engine-specific output directory."""
    page_suffix = f"_page_{result.page_number}"
    output_dir = output_root / {
        "paddleocr": "paddle",
        "qwen2.5-vl": "qwen",
    }.get(result.engine_used, "routed")
    # Route results are also explicitly persisted by the caller under routed.
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{input_path.stem}{page_suffix}.json"
    destination.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return destination


def save_routed_result(output_root: Path, result: OCRResult, input_path: Path) -> Path:
    """Save the router-selected output independently of the winning engine."""
    output_dir = output_root / "routed"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{input_path.stem}_page_{result.page_number}.json"
    destination.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return destination
