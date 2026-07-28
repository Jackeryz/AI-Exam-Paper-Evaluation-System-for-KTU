"""CLI for the confidence-routed PaddleOCR/Qwen2.5-VL sandbox experiment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.ocr_sandbox.adaptive_ocr.benchmark import BenchmarkRunner
from experiments.ocr_sandbox.adaptive_ocr.router import OCRRouter
from experiments.ocr_sandbox.adaptive_ocr.storage import save_result, save_routed_result
from experiments.ocr_sandbox.test_ocr import load_pages
from experiments.ocr_sandbox.utils import config


def parse_args() -> argparse.Namespace:
    """Parse adaptive OCR experiment options."""
    parser = argparse.ArgumentParser(description="Run confidence-routed OCR")
    parser.add_argument("input_file", help="PDF or image to transcribe")
    parser.add_argument(
        "--threshold",
        type=float,
        default=config.OCR_CONFIDENCE_THRESHOLD,
        help="Paddle confidence required to avoid Qwen fallback",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        default=config.BENCHMARK_MODE,
        help="Run PaddleOCR and Qwen2.5-VL for every page",
    )
    parser.add_argument(
        "--ground-truth-dir",
        type=Path,
        default=None,
        help="Optional directory containing <input-stem>.txt ground truth files",
    )
    return parser.parse_args()


def main() -> int:
    """Run routed OCR and optionally emit benchmark comparison reports."""
    args = parse_args()
    input_path = Path(args.input_file).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1
    try:
        pages = load_pages(input_path)
    except (RuntimeError, ValueError) as exc:
        print(f"Error loading input: {exc}", file=sys.stderr)
        return 1

    router = OCRRouter(
        confidence_threshold=args.threshold,
        benchmark_mode=args.benchmark,
    )
    benchmark = BenchmarkRunner(router, args.ground_truth_dir) if args.benchmark else None
    for page_number, image in pages:
        try:
            if benchmark:
                record = benchmark.process_page(image, page_number, input_path.name)
                routed_result = record.routed
                save_result(router.output_root, record.paddle, input_path)
                if record.qwen:
                    save_result(router.output_root, record.qwen, input_path)
            else:
                routed_result = router.process(
                    image, page_number=page_number, input_filename=input_path.name
                )
                if router.last_paddle_result:
                    save_result(router.output_root, router.last_paddle_result, input_path)
                if router.last_qwen_result:
                    save_result(router.output_root, router.last_qwen_result, input_path)
            saved_path = save_routed_result(router.output_root, routed_result, input_path)
            print(
                f"Page {page_number}: {routed_result.engine_used} "
                f"(confidence={routed_result.confidence}) -> {saved_path}"
            )
        except Exception as exc:
            print(f"Error processing page {page_number}: {exc}", file=sys.stderr)
            return 1

    if benchmark:
        comparison_path, summary_path = benchmark.write_reports()
        print(f"Benchmark comparison -> {comparison_path}")
        print(f"Benchmark summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
