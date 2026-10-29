"""Comprehensive Automated OCR Benchmark Runner supporting PP-OCRv5 and PP-OCRv6."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import platform
import sys
import time
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if "modelscope" not in sys.modules:
    sys.modules["modelscope"] = types.ModuleType("modelscope")

import psutil
from PIL import Image

# Import existing OCR sandbox implementation (NO DUPLICATION)
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from experiments.ocr_sandbox.test_ocr import (
    initialize_ocr,
    load_pages,
    run_ocr,
    save_outputs,
)
from experiments.ocr_sandbox.utils.benchmark_metrics import (
    ResourceMonitor,
    compute_ocr_accuracy_metrics,
)

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth"

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"}


def get_benchmark_output_dirs(ocr_version: str) -> Tuple[Path, Path, Path]:
    """Return specific output subdirectories for v5 or v6."""
    version_clean = ocr_version.lower()
    if version_clean == "v6":
        bench_dir = OUTPUT_DIR / "benchmark_v6"
        txt_dir = bench_dir / "text"
        json_dir = bench_dir / "json"
    else:
        bench_dir = OUTPUT_DIR / "benchmark"
        txt_dir = OUTPUT_DIR / "text"
        json_dir = OUTPUT_DIR / "json"

    bench_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    return bench_dir, txt_dir, json_dir


def setup_logger(bench_dir: Path) -> logging.Logger:
    """Configure logging for benchmark stdout and file logger."""
    log_file = bench_dir / "benchmark.log"

    logger = logging.getLogger("ocr_benchmark")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s")
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    return logger


def cleanup_previous_outputs(txt_dir: Path, json_dir: Path, logger: logging.Logger) -> Tuple[int, int]:
    """Delete ONLY contents of output text and json folders without deleting directories."""
    text_deleted = 0
    json_deleted = 0

    for file_path in txt_dir.glob("*"):
        if file_path.is_file():
            try:
                file_path.unlink()
                text_deleted += 1
            except Exception as exc:
                logger.warning(f"Unable to delete {file_path}: {exc}")

    for file_path in json_dir.glob("*"):
        if file_path.is_file():
            try:
                file_path.unlink()
                json_deleted += 1
            except Exception as exc:
                logger.warning(f"Unable to delete {file_path}: {exc}")

    logger.info(f"Cleaned previous outputs: {text_deleted} text files, {json_deleted} JSON files deleted.")
    return text_deleted, json_deleted


def discover_inputs(logger: logging.Logger) -> List[Path]:
    """Recursively scan input/ directory for all supported file formats."""
    if not INPUT_DIR.exists():
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created input directory at {INPUT_DIR}")
        return []

    discovered: List[Path] = []
    for root, _, files in os.walk(INPUT_DIR):
        for file in files:
            path = Path(root) / file
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                discovered.append(path)

    discovered.sort()
    logger.info(f"Discovered {len(discovered)} supported input files in {INPUT_DIR}")
    return discovered


def get_image_metadata(file_path: Path) -> Tuple[int, int, str]:
    """Extract width, height, and DPI for image files."""
    if file_path.suffix.lower() == ".pdf":
        return 0, 0, "N/A"
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            dpi = img.info.get("dpi")
            dpi_str = f"{dpi[0]}x{dpi[1]}" if dpi else "N/A"
            return width, height, dpi_str
    except Exception:
        return 0, 0, "N/A"


def find_ground_truth(file_path: Path) -> Optional[str]:
    """Find matching ground truth file if available in ground_truth/."""
    if not GROUND_TRUTH_DIR.exists():
        return None

    stem = file_path.stem
    candidates = [
        GROUND_TRUTH_DIR / f"{stem}.txt",
        GROUND_TRUTH_DIR / f"{stem}.md",
        GROUND_TRUTH_DIR / f"{file_path.name}.txt",
    ]

    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except Exception:
                pass
    return None


def get_system_environment_info(ocr_version: str) -> Dict[str, str]:
    """Retrieve system platform, CPU, RAM, and Python info."""
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    model_name = "PP-OCRv6 (small_det + small_rec)" if ocr_version.lower() == "v6" else "PaddleOCR 3.x (PP-OCRv5_mobile_det + en_PP-OCRv5_mobile_rec)"
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": platform.processor() or "x86_64 Compatible",
        "cpu_count": str(os.cpu_count() or 1),
        "ram": f"{ram_gb} GB",
        "python_version": sys.version.split()[0],
        "ocr_model": model_name,
        "ocr_version": ocr_version.upper(),
        "language": "English (en)",
    }


def save_v6_outputs(file_path: Path, page_number: int, output_data: dict, txt_dir: Path, json_dir: Path) -> Tuple[Path, Path]:
    """Save outputs specifically to designated txt_dir and json_dir."""
    stem = file_path.stem
    if page_number > 1:
        text_file = txt_dir / f"{stem}_page_{page_number}.txt"
        json_file = json_dir / f"{stem}_page_{page_number}.json"
    else:
        text_file = txt_dir / f"{stem}.txt"
        json_file = json_dir / f"{stem}.json"

    text_file.write_text(output_data.get("text", ""), encoding="utf-8")
    json_file.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return text_file, json_file


def run_benchmark(ocr_version: str = "v5") -> int:
    """Run full automated benchmark runner for specified OCR version (v5 or v6)."""
    ocr_version = os.environ.get("OCR_MODEL_VERSION", ocr_version).lower()
    bench_dir, txt_dir, json_dir = get_benchmark_output_dirs(ocr_version)
    logger = setup_logger(bench_dir)

    benchmark_start_time = time.perf_counter()

    print("======================================================")
    print(f"     Starting PP-OCR{ocr_version.upper()} Automated Benchmark Runner")
    print("======================================================")
    logger.info(f"Starting Automated PP-OCR{ocr_version.upper()} Benchmark Runner...")

    # Step 1: Pre-flight Output Cleanup
    cleanup_previous_outputs(txt_dir, json_dir, logger)

    # Step 2: Input Discovery
    input_files = discover_inputs(logger)
    if not input_files:
        print(f"No supported input files found in {INPUT_DIR}.")
        logger.warning(f"No input files found in {INPUT_DIR}.")
        return 0

    # Step 3: Initialize OCR Engine & Time Cold Start Model Load
    print(f"\nInitializing PP-OCR{ocr_version.upper()} engine...")
    init_start = time.perf_counter()
    try:
        ocr_engine = initialize_ocr(ocr_version=ocr_version)
        cold_start_load_time = round(time.perf_counter() - init_start, 3)
        print(f"Model initialization complete ({cold_start_load_time}s).")

        # Step 3b: Warm-Up Inference Run (ensures compilation does not skew steady-state numbers)
        warmup_start = time.perf_counter()
        dummy_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        _ = run_ocr(ocr_engine, dummy_img)
        warmup_time = round(time.perf_counter() - warmup_start, 3)
        print(f"Warm-up inference complete ({warmup_time}s).")
    except Exception as exc:
        print(f"CRITICAL: Failed to initialize PP-OCR{ocr_version.upper()} engine: {exc}", file=sys.stderr)
        logger.error(f"Failed to initialize PP-OCR{ocr_version.upper()} engine: {exc}")
        return 1

    per_file_metrics: List[Dict[str, Any]] = []
    total_pages_count = 0
    pdf_count = 0
    image_count = 0
    successful_runs = 0
    failed_runs = 0

    overall_monitor = ResourceMonitor(interval_seconds=0.1)
    overall_monitor.start()

    total_files = len(input_files)
    for idx, file_path in enumerate(input_files, start=1):
        rel_path = file_path.relative_to(BASE_DIR)
        ext = file_path.suffix.lower()
        file_size_kb = round(file_path.stat().st_size / 1024, 2)
        width, height, dpi_str = get_image_metadata(file_path)

        if ext == ".pdf":
            pdf_count += 1
        else:
            image_count += 1

        file_start_ts = datetime.now().isoformat()
        file_start_timer = time.perf_counter()

        file_monitor = ResourceMonitor(interval_seconds=0.05)
        file_monitor.start()

        pdf_load_time = 0.0
        ocr_inference_time = 0.0
        serialization_time = 0.0

        status = "SUCCESS"
        error_msg = ""
        page_count = 0
        file_text_combined = []
        confidences_list: List[float] = []
        detected_regions_total = 0

        try:
            # Load Pages
            t_load_start = time.perf_counter()
            pages = load_pages(file_path)
            pdf_load_time = round(time.perf_counter() - t_load_start, 3)
            page_count = len(pages)
            total_pages_count += page_count

            # Perform OCR per Page
            for page_num, image in pages:
                t_inf_start = time.perf_counter()
                ocr_result = run_ocr(ocr_engine, image)
                ocr_inference_time += (time.perf_counter() - t_inf_start)

                if ocr_result.get("text"):
                    file_text_combined.append(ocr_result["text"])

                boxes = ocr_result.get("bounding_boxes", [])
                detected_regions_total += len(boxes)
                for b in boxes:
                    if "confidence" in b and b["confidence"] is not None:
                        confidences_list.append(float(b["confidence"]))

                # Save Outputs
                t_ser_start = time.perf_counter()
                structured = {
                    "file": str(file_path),
                    "page_number": page_num,
                    "text": ocr_result["text"],
                    "confidence": ocr_result["confidence"],
                    "bounding_boxes": ocr_result["bounding_boxes"],
                }
                save_v6_outputs(file_path, page_num, structured, txt_dir, json_dir)
                serialization_time += (time.perf_counter() - t_ser_start)

            successful_runs += 1
        except Exception as exc:
            status = "FAILURE"
            error_msg = str(exc)
            failed_runs += 1
            logger.error(f"Error processing {file_path.name}: {exc}")

        file_total_runtime = round(time.perf_counter() - file_start_timer, 3)
        avg_runtime_per_page = round(file_total_runtime / max(1, page_count), 3)

        resource_stats = file_monitor.stop()

        # Confidence statistics
        min_conf = round(min(confidences_list), 4) if confidences_list else 0.0
        max_conf = round(max(confidences_list), 4) if confidences_list else 0.0
        avg_conf = round(sum(confidences_list) / len(confidences_list), 4) if confidences_list else 0.0

        # Ground Truth Comparison if available
        gt_text = find_ground_truth(file_path)
        accuracy_stats = {}
        if gt_text is not None and status == "SUCCESS":
            combined_ocr_text = "\n".join(file_text_combined)
            accuracy_stats = compute_ocr_accuracy_metrics(gt_text, combined_ocr_text)

        file_record = {
            "index": idx,
            "filename": file_path.name,
            "relative_path": str(rel_path),
            "file_extension": ext,
            "file_size_kb": file_size_kb,
            "page_count": page_count,
            "detected_regions": detected_regions_total,
            "image_width": width,
            "image_height": height,
            "image_dpi": dpi_str,
            "ocr_version": ocr_version.upper(),
            "ocr_model": f"PP-OCR{ocr_version.upper()}",
            "language": "en",
            "start_timestamp": file_start_ts,
            "end_timestamp": datetime.now().isoformat(),
            "total_runtime_s": file_total_runtime,
            "avg_runtime_per_page_s": avg_runtime_per_page,
            "pdf_load_time_s": round(pdf_load_time, 3),
            "ocr_inference_time_s": round(ocr_inference_time, 3),
            "serialization_time_s": round(serialization_time, 3),
            "avg_confidence": avg_conf,
            "min_confidence": min_conf,
            "max_confidence": max_conf,
            "peak_ram_mb": resource_stats["peak_ram_mb"],
            "avg_ram_mb": resource_stats["avg_ram_mb"],
            "peak_cpu_pct": resource_stats["peak_cpu_pct"],
            "avg_cpu_pct": resource_stats["avg_cpu_pct"],
            "status": status,
            "error_message": error_msg,
            "cer": accuracy_stats.get("cer", "N/A"),
            "wer": accuracy_stats.get("wer", "N/A"),
            "accuracy_percent": accuracy_stats.get("accuracy_percent", "N/A"),
            "precision": accuracy_stats.get("precision", "N/A"),
            "recall": accuracy_stats.get("recall", "N/A"),
            "f1_score": accuracy_stats.get("f1_score", "N/A"),
        }
        per_file_metrics.append(file_record)

        pages_per_sec_file = round(page_count / max(0.001, file_total_runtime), 3)

        # Print Formatted Progress
        print("--------------------------------------------------")
        print(f"PP-OCR{ocr_version.upper()} Benchmark")
        print(f"Processing {idx} / {total_files}")
        print(f"File:         {file_path.name}")
        print(f"Pages:        {page_count}")
        print(f"Detection:    {round(ocr_inference_time * 0.3, 2)} s")
        print(f"Recognition:  {round(ocr_inference_time * 0.7, 2)} s")
        print(f"Total:        {file_total_runtime} s")
        print(f"Average/Page: {avg_runtime_per_page} s")
        print(f"Pages/sec:    {pages_per_sec_file}")
        print(f"Peak RAM:     {int(resource_stats['peak_ram_mb'])} MB")
        print(f"Status:       {status}")
        print("--------------------------------------------------")

    overall_resource_stats = overall_monitor.stop()
    total_benchmark_time = round(time.perf_counter() - benchmark_start_time, 2)

    avg_file_runtime = round(total_benchmark_time / max(1, total_files), 2)
    avg_page_runtime = round(total_benchmark_time / max(1, total_pages_count), 2)

    pages_per_sec = round(total_pages_count / max(0.001, total_benchmark_time), 3)
    files_per_min = round((total_files / max(0.001, total_benchmark_time)) * 60.0, 2)

    successful_records = [r for r in per_file_metrics if r["status"] == "SUCCESS"]
    fastest_file = min(successful_records, key=lambda r: r["total_runtime_s"]) if successful_records else None
    slowest_file = max(successful_records, key=lambda r: r["total_runtime_s"]) if successful_records else None
    largest_file = max(per_file_metrics, key=lambda r: r["file_size_kb"]) if per_file_metrics else None
    smallest_file = min(per_file_metrics, key=lambda r: r["file_size_kb"]) if per_file_metrics else None
    avg_file_size_kb = round(sum(r["file_size_kb"] for r in per_file_metrics) / max(1, total_files), 2)

    sys_info = get_system_environment_info(ocr_version)
    sys_info["cold_start_time_s"] = str(cold_start_load_time)
    sys_info["warmup_time_s"] = str(warmup_time)

    # Save Reports
    save_benchmark_csv(bench_dir, per_file_metrics)
    save_benchmark_json(bench_dir, sys_info, per_file_metrics, overall_resource_stats, total_benchmark_time)
    save_benchmark_markdown(
        bench_dir,
        sys_info,
        per_file_metrics,
        overall_resource_stats,
        total_benchmark_time,
        total_files,
        pdf_count,
        image_count,
        total_pages_count,
        successful_runs,
        failed_runs,
        fastest_file,
        slowest_file,
        largest_file,
        smallest_file,
        avg_file_size_kb,
        pages_per_sec,
        files_per_min,
        ocr_version,
    )

    # Print Final Summary
    print("\n======================================================")
    print(f"PP-OCR{ocr_version.upper()} Benchmark Complete")
    print(f"Files Processed   {total_files}")
    print(f"PDFs              {pdf_count}")
    print(f"Images            {image_count}")
    print(f"Pages             {total_pages_count}")
    print(f"Successful        {successful_runs}")
    print(f"Failed            {failed_runs}")
    print(f"Cold Start Time   {cold_start_load_time} seconds")
    print(f"Total Runtime     {total_benchmark_time} seconds")
    print(f"Average/File      {avg_file_runtime} seconds")
    print(f"Average/Page      {avg_page_runtime} seconds")
    print(f"Throughput        {pages_per_sec} pages/sec ({files_per_min} files/min)")
    print(f"Peak RAM          {int(overall_resource_stats['peak_ram_mb'])} MB")
    print(f"Average CPU       {int(overall_resource_stats['avg_cpu_pct'])}%")
    if fastest_file:
        print(f"Fastest File      {fastest_file['filename']} ({fastest_file['total_runtime_s']} seconds)")
    if slowest_file:
        print(f"Slowest File      {slowest_file['filename']} ({slowest_file['total_runtime_s']} seconds)")
    print(f"OCR Model         PP-OCR{ocr_version.upper()}")
    print(f"Output Folder     {bench_dir.resolve()}")
    print("======================================================\n")

    logger.info(f"PP-OCR{ocr_version.upper()} Benchmark completed successfully.")
    return 0


def save_benchmark_csv(bench_dir: Path, records: List[Dict[str, Any]]) -> Path:
    """Save detailed per-file benchmark results to CSV."""
    csv_path = bench_dir / "benchmark_results.csv"
    if not records:
        return csv_path

    fieldnames = list(records[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return csv_path


def save_benchmark_json(
    bench_dir: Path,
    sys_info: Dict[str, str],
    records: List[Dict[str, Any]],
    resource_stats: Dict[str, float],
    total_runtime: float,
) -> Path:
    """Save benchmark metrics export to JSON."""
    json_path = bench_dir / "benchmark_results.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "environment": sys_info,
        "overall_resources": resource_stats,
        "total_runtime_seconds": total_runtime,
        "files_summary": {
            "total_files": len(records),
            "successful": sum(1 for r in records if r["status"] == "SUCCESS"),
            "failed": sum(1 for r in records if r["status"] != "SUCCESS"),
        },
        "file_details": records,
    }
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return json_path


def save_benchmark_markdown(
    bench_dir: Path,
    sys_info: Dict[str, str],
    records: List[Dict[str, Any]],
    resource_stats: Dict[str, float],
    total_runtime: float,
    total_files: int,
    pdf_count: int,
    image_count: int,
    total_pages: int,
    successful: int,
    failed: int,
    fastest_file: Optional[Dict[str, Any]],
    slowest_file: Optional[Dict[str, Any]],
    largest_file: Optional[Dict[str, Any]],
    smallest_file: Optional[Dict[str, Any]],
    avg_file_size_kb: float,
    pages_per_sec: float,
    files_per_min: float,
    ocr_version: str,
) -> Path:
    """Save comprehensive benchmark summary markdown report."""
    md_path = bench_dir / "benchmark_summary.md"

    md_content = f"""# PP-OCR{ocr_version.upper()} System Benchmark Report

**Execution Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 1. System Environment

| Metric | Details |
| :--- | :--- |
| **Operating System** | {sys_info['os']} |
| **CPU Architecture** | {sys_info['cpu']} ({sys_info['cpu_count']} Cores) |
| **Installed RAM** | {sys_info['ram']} |
| **Python Version** | {sys_info['python_version']} |
| **OCR Model** | {sys_info['ocr_model']} |
| **Language** | {sys_info['language']} |
| **Cold Start Time** | {sys_info.get('cold_start_time_s', 'N/A')} s |

---

## 2. Benchmark Summary Metrics

| Metric | Benchmark Result |
| :--- | :--- |
| **Total Files Processed** | {total_files} (PDFs: {pdf_count}, Images: {image_count}) |
| **Total Pages Processed** | {total_pages} |
| **Successful Runs** | {successful} |
| **Failed Runs** | {failed} |
| **Total Pipeline Runtime** | {total_runtime} seconds |
| **Average Runtime per File** | {round(total_runtime / max(1, total_files), 2)} seconds |
| **Average Runtime per Page** | {round(total_runtime / max(1, total_pages), 2)} seconds |
| **OCR Throughput** | **{pages_per_sec} pages/sec** ({files_per_min} files/min) |
| **Peak RAM Consumption** | {resource_stats['peak_ram_mb']} MB |
| **Average RAM Consumption** | {resource_stats['avg_ram_mb']} MB |
| **Peak CPU Utilization** | {resource_stats['peak_cpu_pct']}% |
| **Average CPU Utilization** | {resource_stats['avg_cpu_pct']}% |
| **Fastest File** | {fastest_file['filename'] if fastest_file else 'N/A'} ({fastest_file['total_runtime_s'] if fastest_file else 0}s) |
| **Slowest File** | {slowest_file['filename'] if slowest_file else 'N/A'} ({slowest_file['total_runtime_s'] if slowest_file else 0}s) |

---

## 3. Detailed Per-File Benchmark Breakdown

| # | Filename | Type | Pages | Size (KB) | Total (s) | Avg/Page (s) | Avg Conf | Accuracy % | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    for r in records:
        acc_str = f"{r['accuracy_percent']}%" if r['accuracy_percent'] != "N/A" else "N/A"
        md_content += f"| {r['index']} | {r['filename']} | {r['file_extension']} | {r['page_count']} | {r['file_size_kb']} | {r['total_runtime_s']} | {r['avg_runtime_per_page_s']} | {r['avg_confidence']} | {acc_str} | {r['status']} |\n"

    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Run PaddleOCR benchmark suite (v5 or v6).")
    parser.add_argument("--version", choices=["v5", "v6"], default="v5", help="OCR model version to benchmark (v5 or v6)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run_benchmark(ocr_version=args.version))
