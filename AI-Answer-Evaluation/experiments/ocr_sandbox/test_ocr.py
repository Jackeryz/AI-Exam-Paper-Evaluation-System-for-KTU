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
import types
from pathlib import Path
from typing import Any, List, Tuple

# Bypass broken optional modelscope/torch DLL dependency on Windows if uninitialized
if "modelscope" not in sys.modules:
    sys.modules["modelscope"] = types.ModuleType("modelscope")

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
    ocr_version: str = "v5",
) -> Any:
    """Create a PaddleOCR engine configured for English text using local model directories (v5 or v6)."""
    os.environ.setdefault("FLAGS_use_onednn", "false")
    os.environ.setdefault("FLAGS_use_mkldnn", "false")
    os.environ.setdefault("PADDLE_DISABLE_MKL", "True")
    os.environ.setdefault("CPU_NUM", "1")

    project_root = Path(__file__).resolve().parents[2]
    configured_model_root = os.environ.get("PADDLEOCR_MODEL_ROOT")
    local_model_root = Path(configured_model_root).expanduser().resolve() if configured_model_root else project_root / "models" / "paddleocr"

    version_clean = ocr_version.lower()
    if version_clean == "v6":
        det_dir = local_model_root / "v6" / "det"
        rec_dir = local_model_root / "v6" / "rec"
        det_model_name = "PP-OCRv6_small_det"
        rec_model_name = "PP-OCRv6_small_rec"
    else:
        # Default v5
        v5_det = local_model_root / "v5" / "det"
        det_dir = v5_det if v5_det.exists() else local_model_root / "det"
        v5_rec = local_model_root / "v5" / "rec"
        rec_dir = v5_rec if v5_rec.exists() else local_model_root / "rec"
        det_model_name = "PP-OCRv5_mobile_det"
        rec_model_name = "en_PP-OCRv5_mobile_rec"

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
                f"PaddleOCR {ocr_version.upper()} models not found.\n\n"
                "Expected:\n"
                f"{expected_paths}\n\n"
                "Please place the official PaddleOCR model files in these folders before running the sandbox.",
                file=sys.stderr,
            )
            raise RuntimeError(f"Local PaddleOCR {ocr_version.upper()} model directories are missing or empty")

    try:
        from paddleocr import PaddleOCR
    except Exception as exc:
        raise RuntimeError(f"Unable to import PaddleOCR: {exc}") from exc

    try:
        return PaddleOCR(
            text_detection_model_name=det_model_name,
            text_detection_model_dir=str(det_dir),
            text_recognition_model_name=rec_model_name,
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
        result = ocr_engine.predict(image_array)

    if not result:
        return {
            "text": "",
            "confidence": 0.0,
            "bounding_boxes": [],
        }

    lines: List[str] = []
    scores: List[float] = []
    bounding_boxes: List[dict] = []

    for item in result:
        if isinstance(item, dict):
            rec_texts = item.get("rec_texts", [])
            rec_scores = item.get("rec_scores", [])
            rec_boxes = item.get("rec_boxes", [])

            for index, line_text in enumerate(rec_texts):
                score = float(rec_scores[index]) if index < len(rec_scores) else 0.0
                raw_box = rec_boxes[index] if index < len(rec_boxes) else []
                box = convert_box_format(raw_box)

                lines.append(line_text)
                scores.append(score)
                bounding_boxes.append(
                    {
                        "text": line_text,
                        "confidence": round(score, 4),
                        "bbox": box,
                    }
                )
        elif isinstance(item, (list, tuple)):
            for element in item:
                if (
                    isinstance(element, (list, tuple))
                    and len(element) == 2
                    and isinstance(element[1], (list, tuple))
                ):
                    box = convert_box_format(element[0])
                    text_tuple = element[1]
                    line_text = text_tuple[0]
                    score = float(text_tuple[1])

                    lines.append(line_text)
                    scores.append(score)
                    bounding_boxes.append(
                        {
                            "text": line_text,
                            "confidence": round(score, 4),
                            "bbox": box,
                        }
                    )

    combined_text = "\n".join(lines)
    average_confidence = float(np.mean(scores)) if scores else 0.0

    return {
        "text": combined_text,
        "confidence": round(average_confidence, 4),
        "bounding_boxes": bounding_boxes,
    }


def convert_box_format(box_data: Any) -> list:
    """Normalize bounding box points into a list of 4 [x, y] coordinates."""
    if isinstance(box_data, np.ndarray):
        box_data = box_data.tolist()

    if (
        isinstance(box_data, (list, tuple))
        and len(box_data) == 4
        and all(isinstance(point, (list, tuple)) and len(point) == 2 for point in box_data)
    ):
        return [[float(point[0]), float(point[1])] for point in box_data]

    if (
        isinstance(box_data, (list, tuple))
        and len(box_data) == 4
        and all(isinstance(val, (int, float)) for val in box_data)
    ):
        x1, y1, x2, y2 = [float(v) for v in box_data]
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    return []


def save_outputs(
    input_path: Path, page_number: int, output_data: dict
) -> Tuple[Path, Path]:
    """Save formatted OCR outputs as plain text and JSON files."""
    ensure_output_dirs()

    stem = input_path.stem
    if page_number > 1:
        text_filename = f"{stem}_page_{page_number}.txt"
        json_filename = f"{stem}_page_{page_number}.json"
    else:
        text_filename = f"{stem}.txt"
        json_filename = f"{stem}.json"

    text_path = TEXT_OUTPUT_DIR / text_filename
    json_path = JSON_OUTPUT_DIR / json_filename

    text_path.write_text(output_data.get("text", ""), encoding="utf-8")
    json_path.write_text(
        json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return text_path, json_path


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for single-file OCR processing."""
    parser = argparse.ArgumentParser(
        description="Run PaddleOCR on a PDF or image file and output extracted text and JSON."
    )
    parser.add_argument("input_path", type=str, help="Path to the PDF or image file")
    return parser.parse_args()


def main() -> int:
    """CLI entry point for processing a single file."""
    args = parse_arguments()
    input_path = Path(args.input_path).resolve()

    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        return 1

    try:
        pages = load_pages(input_path)
    except Exception as exc:
        print(f"Error loading pages from '{input_path}': {exc}", file=sys.stderr)
        return 1

    try:
        ocr = initialize_ocr()
    except Exception as exc:
        print(f"Error initializing OCR engine: {exc}", file=sys.stderr)
        return 1

    print(f"Processing '{input_path.name}' ({len(pages)} page(s))...")

    for page_number, image in pages:
        result = run_ocr(ocr, image)
        structured_output = {
            "file": str(input_path),
            "page_number": page_number,
            "text": result["text"],
            "confidence": result["confidence"],
            "bounding_boxes": result["bounding_boxes"],
        }
        text_file, json_file = save_outputs(input_path, page_number, structured_output)

        print(f"\n--- Page {page_number} ---")
        print(result["text"])
        print(f"\nSaved outputs:\n  Text -> {text_file}\n  JSON -> {json_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
