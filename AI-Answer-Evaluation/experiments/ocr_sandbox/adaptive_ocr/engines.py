"""OCR strategy implementations with a shared result contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from PIL import Image

from experiments.ocr_sandbox.utils import config

from .models import OCRResult


class BaseOCR(ABC):
    """Abstract OCR strategy used by :class:`OCRRouter`."""

    engine_name: str

    @abstractmethod
    def process(self, image: Image.Image, page_number: int) -> OCRResult:
        """Transcribe one preprocessed page into the common result format."""


class PaddleOCRStrategy(BaseOCR):
    """Adapter around the sandbox's existing local PaddleOCR implementation."""

    engine_name = "paddleocr"

    def __init__(self, engine: Any | None = None) -> None:
        self._engine = engine

    @property
    def engine(self) -> Any:
        """Lazily initialize PaddleOCR through the existing sandbox helper."""
        if self._engine is None:
            from experiments.ocr_sandbox.test_ocr import initialize_ocr

            self._engine = initialize_ocr()
        return self._engine

    def process(self, image: Image.Image, page_number: int) -> OCRResult:
        """Run PaddleOCR and normalize its existing sandbox result."""
        from experiments.ocr_sandbox.test_ocr import run_ocr

        started_at = perf_counter()
        raw_result = run_ocr(self.engine, image)
        return OCRResult(
            text=raw_result["text"],
            confidence=float(raw_result["confidence"]),
            processing_time=perf_counter() - started_at,
            engine_used=self.engine_name,
            page_number=page_number,
            bounding_boxes=raw_result["bounding_boxes"],
        )


class QwenOCRStrategy(BaseOCR):
    """Lazy Qwen2.5-VL transcription strategy with automatic CPU fallback."""

    engine_name = "qwen2.5-vl"

    def __init__(self, model: Any | None = None, processor: Any | None = None) -> None:
        self._model = model
        self._processor = processor
        self._device: str | None = None

    def _load(self) -> None:
        """Load Qwen and select CUDA when available, otherwise CPU."""
        if self._model is not None and self._processor is not None:
            return
        try:
            import torch
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        except ImportError as exc:
            raise RuntimeError(
                "Qwen fallback requires the optional sandbox dependencies. "
                "Install experiments/ocr_sandbox/requirements.txt."
            ) from exc

        use_cuda = config.QWEN_DEVICE_PREFERENCE == "auto" and torch.cuda.is_available()
        self._device = "cuda" if use_cuda else "cpu"
        dtype = torch.float16 if use_cuda else torch.float32
        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            config.QWEN_MODEL_ID,
            torch_dtype=dtype,
        ).to(self._device)
        self._model.eval()
        self._processor = AutoProcessor.from_pretrained(config.QWEN_MODEL_ID)

    def process(self, image: Image.Image, page_number: int) -> OCRResult:
        """Transcribe a page with Qwen2.5-VL using the shared preprocessed image."""
        self._load()
        assert self._model is not None and self._processor is not None
        started_at = perf_counter()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": config.QWEN_PROMPT},
                ],
            }
        ]
        prompt = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(
            text=[prompt], images=[image], padding=True, return_tensors="pt"
        ).to(self._device)
        generated_ids = self._model.generate(
            **inputs, max_new_tokens=config.QWEN_MAX_NEW_TOKENS
        )
        generated_text = self._processor.batch_decode(
            generated_ids[:, inputs.input_ids.shape[1] :],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return OCRResult(
            text=generated_text.strip(),
            confidence=None,
            processing_time=perf_counter() - started_at,
            engine_used=self.engine_name,
            page_number=page_number,
            bounding_boxes=[],
        )
