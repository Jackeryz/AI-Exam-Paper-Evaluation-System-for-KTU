"""Shared types for modular OCR strategies and routed results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


PageClassification = Literal["PRINTED", "HANDWRITTEN", "MIXED"]


@dataclass(slots=True)
class OCRResult:
    """Normalized OCR output returned by every strategy and the router."""

    text: str
    confidence: float | None
    processing_time: float
    engine_used: str
    page_number: int
    bounding_boxes: list[dict[str, Any]] = field(default_factory=list)
    page_classification: PageClassification | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a JSON-safe dictionary."""
        return asdict(self)
