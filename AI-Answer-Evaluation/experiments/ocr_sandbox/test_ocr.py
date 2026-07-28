"""Standalone OCR test script for the OCR sandbox.

This script accepts a PDF or image file path as a command-line argument,
runs PaddleOCR on each page/image, prints the extracted text, and saves
plain-text and JSON outputs under the sandbox output folders.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, List, Tuple

import fitz
import numpy as np
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
TEXT_OUTPUT_DIR = BASE_DIR / "output" / "text"
JSON_OUTPUT_DIR = BASE_DIR / "output" / "json"


def ensure_output_dirs() -> None:
    """Create output directories if they do not already exist."""
    TEXT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_pages(input_path: Path) -> List[Tuple[int, Image.Image]]:
    """Load image pages from a PDF or from a single image file."""
    suffix = input_path.suffix.lower()

    if suffix == ".pdf":
        pages: List[Tuple[int, Image.Image]] = []
        try:
            doc = fitz.open(input_path)
        except Exception as exc:
            raise RuntimeError(f"Unable to open PDF: {exc}") from exc

        for page_number in range(len(doc)):
            page = doc[page_number]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append((page_number + 1, image))
        doc.close()
        return pages

    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        try:
            image = Image.open(input_path).convert("RGB")
        except Exception as exc:
            raise RuntimeError(f"Unable to read image: {exc}") from exc
        return [(1, image)]

    raise ValueError("Unsupported file type. Use a PDF or a common image format.")


def initialize_ocr(
    use_doc_orientation_classify: bool = False,
    use_doc_unwarping: bool = False,
    use_textline_orientation: bool = False,
) -> Any:
    """Create a PaddleOCR engine configured for English text using local model directories."""
    os.environ.setdefault("FLAGS_use_onednn", "false")
    os.environ.setdefault("FLAGS_use_mkldnn", "false")
    os.environ.setdefault("PADDLE_DISABLE_MKL", "True")
    os.environ.setdefault("CPU_NUM", "1")

    project_root = Path(__file__).resolve().parents[2]
    configured_model_root = os.environ.get("PADDLEOCR_MODEL_ROOT")
    local_model_root = Path(configured_model_root).expanduser().resolve() if configured_model_root else project_root / "models" / "paddleocr"
    det_dir = local_model_root / "det"
    rec_dir = local_model_root / "rec"
    cls_dir = local_model_root / "cls"

    required_dirs = {
        "det": det_dir,
        "rec": rec_dir,
    }
    if use_doc_orientation_classify:
        required_dirs["cls"] = cls_dir

    expected_paths = "\n".join(f"- {path}" for path in required_dirs.values())

    for directory in required_dirs.values():
        if not directory.exists() or not any(directory.iterdir()):
            print(
                "PaddleOCR models not found.\n\n"
                "Expected:\n"
                f"{expected_paths}\n\n"
                "Please place the official PaddleOCR model files in these folders before running the sandbox.",
                file=sys.stderr,
            )
            raise RuntimeError("Local PaddleOCR model directories are missing or empty")

    try:
        from paddleocr import PaddleOCR
    except Exception as exc:
        raise RuntimeError(f"Unable to import PaddleOCR: {exc}") from exc

    try:
        return PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir=str(det_dir),
            text_recognition_model_name="en_PP-OCRv5_mobile_rec",
            text_recognition_model_dir=str(rec_dir),
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            enable_mkldnn=False,
        )
    except Exception as exc:
        if "HTTPSConnectionPool" in str(exc) or "NameResolutionError" in str(exc) or "download" in str(exc).lower():
            raise RuntimeError(
                "PaddleOCR model download failed due to network access. "
                "Install the required model files manually or run this script on a network-enabled machine."
            ) from exc
        raise RuntimeError(f"Unable to initialize PaddleOCR: {exc}") from exc


def run_ocr(ocr_engine: Any, image: Image.Image) -> dict:
    """Run OCR on a single image and return structured results."""
    image_array = np.array(image)

    try:
        result = list(ocr_engine.predict(image_array))
    except TypeError:
        result = ocr_engine.ocr(image_array)

    lines = []
    texts = []
    confidences = []

    if result:
        detected = result[0] if isinstance(result, (list, tuple)) else result
        # PaddleOCR 3.x returns an OCRResult mapping rather than the legacy
        # ``[[box, (text, score)], ...]`` structure.
        if isinstance(detected, dict) and "rec_texts" in detected:
            for text, confidence, bbox in zip(
                detected["rec_texts"],
                detected.get("rec_scores", []),
                detected.get("rec_boxes", []),
            ):
                bbox_values = bbox.tolist() if hasattr(bbox, "tolist") else bbox
                if len(bbox_values) == 4 and not isinstance(
                    bbox_values[0], (list, tuple)
                ):
                    left, top, right, bottom = (int(value) for value in bbox_values)
                    normalized_bbox = [
                        [left, top],
                        [right, top],
                        [right, bottom],
                        [left, bottom],
                    ]
                else:
                    normalized_bbox = [
                        [int(point[0]), int(point[1])] for point in bbox_values
                    ]
                lines.append(
                    {
                        "text": str(text),
                        "confidence": round(float(confidence), 3),
                        "bbox": normalized_bbox,
                    }
                )
                texts.append(str(text))
                confidences.append(float(confidence))
            return {
                "text": "\n".join(texts).strip(),
                "confidence": round(sum(confidences) / len(confidences), 3)
                if confidences
                else 0.0,
                "bounding_boxes": lines,
            }
        if isinstance(detected, list):
            for line in detected:
                if not line:
                    continue
                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    confidence = float(line[1][1]) if isinstance(line[1], (list, tuple)) and len(line[1]) > 1 else 0.0
                    bbox = [[int(point[0]), int(point[1])] for point in line[0]] if isinstance(line[0], (list, tuple)) else []
                    lines.append({
                        "text": text,
                        "confidence": round(confidence, 3),
                        "bbox": bbox,
                    })
                    texts.append(text)
                    confidences.append(confidence)

    combined_text = "\n".join(texts).strip()
    average_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

    return {
        "text": combined_text,
        "confidence": average_confidence,
        "bounding_boxes": lines,
    }


def save_outputs(input_path: Path, page_number: int, output_data: dict) -> Tuple[Path, Path]:
    """Save the OCR text and JSON outputs for a single page/image."""
    stem = input_path.stem
    if page_number > 1:
        text_file = TEXT_OUTPUT_DIR / f"{stem}_page_{page_number}.txt"
        json_file = JSON_OUTPUT_DIR / f"{stem}_page_{page_number}.json"
    else:
        text_file = TEXT_OUTPUT_DIR / f"{stem}.txt"
        json_file = JSON_OUTPUT_DIR / f"{stem}.json"

    text_file.write_text(output_data["text"], encoding="utf-8")
    json_file.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return text_file, json_file


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run PaddleOCR on a PDF or image file")
    parser.add_argument("input_file", help="Path to a PDF or image file")
    return parser.parse_args()


def main() -> int:
    """Entry point for the OCR sandbox script."""
    args = parse_args()
    input_path = Path(args.input_file).expanduser().resolve()

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    ensure_output_dirs()

    try:
        pages = load_pages(input_path)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        ocr_engine = initialize_ocr()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Processing: {input_path}")

    for page_number, image in pages:
        print(f"\n=== Page {page_number} ===")
        try:
            ocr_result = run_ocr(ocr_engine, image)
        except Exception as exc:
            print(f"Error processing page {page_number}: {exc}", file=sys.stderr)
            continue

        print(ocr_result["text"] or "No text detected.")

        structured_result = {
            "file": str(input_path),
            "page_number": page_number,
            "text": ocr_result["text"],
            "confidence": ocr_result["confidence"],
            "bounding_boxes": ocr_result["bounding_boxes"],
        }

        text_file, json_file = save_outputs(input_path, page_number, structured_result)
        print(f"Saved text -> {text_file}")
        print(f"Saved JSON -> {json_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
