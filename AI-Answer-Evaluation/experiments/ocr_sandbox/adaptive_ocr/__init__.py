"""Modular adaptive OCR experiment built around PaddleOCR and Qwen2.5-VL."""

from .models import OCRResult
from .router import OCRRouter

__all__ = ["OCRResult", "OCRRouter"]
