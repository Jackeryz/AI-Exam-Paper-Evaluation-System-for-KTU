"""Comprehensive Automated OCR Benchmark Runner for the OCR Sandbox."""

from __future__ import annotations

import csv
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
from PIL import Image

# Import existing OCR sandbox implementation (NO DUPLICATION)
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]

# Ensure project root is in sys.path
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
TEXT_OUTPUT_DIR = OUTPUT_DIR / "text"
JSON_OUTPUT_DIR = OUTPUT_DIR / "json"
BENCHMARK_OUTPUT_DIR = OUTPUT_DIR / "benchmark"
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth"

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"}


def setup_logger() -> logging.Logger:
    """Configure logging for benchmark stdout and file logger."""
    BENCHMARK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_file = BENCHMARK_OUTPUT_DIR / "benchmark.log"

    logger = logging.getLogger("ocr_benchmark")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s")
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    return logger


def cleanup_previous_outputs(logger: logging.Logger) -> Tuple[int, int]:
    """Delete ONLY contents of output/text/ and output/json/ without deleting directories."""
    TEXT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    text_deleted = 0
    json_deleted = 0

    for file_path in TEXT_OUTPUT_DIR.glob("*"):
        if file_path.is_file():
            try:
                file_path.unlink()
                text_deleted += 1
            except Exception as exc:
                logger.warning(f"Unable to delete {file_path}: {exc}")

    for file_path in JSON_OUTPUT_DIR.glob("*"):
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


def get_system_environment_info() -> Dict[str, str]:
    """Retrieve system platform, CPU, RAM, and Python info."""
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": platform.processor() or "x86_64 Compatible",
        "cpu_count": str(os.cpu_count() or 1),
        "ram": f"{ram_gb} GB",
        "python_version": sys.version.split()[0],
        "ocr_model": "PaddleOCR 3.x (PP-OCRv5_mobile_det + en_PP-OCRv5_mobile_rec)",
        "language": "English (en)",
    }


def run_benchmark() -> int:
    """Run full automated benchmark runner."""
    logger = setup_logger()
    benchmark_start_time = time.perf_counter()

    print("======================================================")
    print("        Starting Automated OCR Benchmark Runner       ")
    print("======================================================")
    logger.info("Starting Automated OCR Benchmark Runner...")

    # Step 1: Pre-flight Output Cleanup
    cleanup_previous_outputs(logger)

    # Step 2: Input Discovery
    input_files = discover_inputs(logger)
    if not input_files:
        print(f"No supported input files found in {INPUT_DIR}.")
        print("Please place sample PDFs or images in experiments/ocr_sandbox/input/")
        logger.warning(f"No input files found in {INPUT_DIR}.")
        return 0

    # Step 3: Initialize OCR Engine & Time Model Load
    print("\nInitializing PaddleOCR 3.x engine...")
    init_start = time.perf_counter()
    try:
        ocr_engine = initialize_ocr()
        model_load_time = round(time.perf_counter() - init_start, 3)
        print(f"Model initialization complete ({model_load_time}s).")
    except Exception as exc:
        print(f"CRITICAL: Failed to initialize OCR engine: {exc}", file=sys.stderr)
        logger.error(f"Failed to initialize OCR engine: {exc}")
        return 1

    # Storage for per-file results
    per_file_metrics: List[Dict[str, Any]] = []
    total_pages_count = 0
    pdf_count = 0
    image_count = 0
    successful_runs = 0
    failed_runs = 0

    overall_monitor = ResourceMonitor(interval_seconds=0.1)
    overall_monitor.start()

    # Step 4: Process Every File
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
        inference_time = 0.0
        text_serialize_time = 0.0
        json_serialize_time = 0.0

        status = "SUCCESS"
        error_msg = ""
        page_count = 0
        file_text_combined = []

        try:
            # 4a. Load Pages
            t_load_start = time.perf_counter()
            pages = load_pages(file_path)
            pdf_load_time = round(time.perf_counter() - t_load_start, 3)
            page_count = len(pages)
            total_pages_count += page_count

            # 4b. Perform OCR per Page
            for page_num, image in pages:
                t_inf_start = time.perf_counter()
                ocr_result = run_ocr(ocr_engine, image)
                inference_time += (time.perf_counter() - t_inf_start)

                if ocr_result.get("text"):
                    file_text_combined.append(ocr_result["text"])

                # 4c. Save Outputs
                t_ser_start = time.perf_counter()
                structured = {
                    "file": str(file_path),
                    "page_number": page_num,
                    "text": ocr_result["text"],
                    "confidence": ocr_result["confidence"],
                    "bounding_boxes": ocr_result["bounding_boxes"],
                }
                txt_file, json_file = save_outputs(file_path, page_num, structured)
                t_ser_end = time.perf_counter()
                text_serialize_time += (t_ser_end - t_ser_start) * 0.5
                json_serialize_time += (t_ser_end - t_ser_start) * 0.5

            successful_runs += 1
        except Exception as exc:
            status = "FAILURE"
            error_msg = str(exc)
            failed_runs += 1
            logger.error(f"Error processing {file_path.name}: {exc}")

        file_total_runtime = round(time.perf_counter() - file_start_timer, 3)
        avg_runtime_per_page = round(file_total_runtime / max(1, page_count), 3)

        resource_stats = file_monitor.stop()

        # 4d. Ground Truth Comparison if available
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
            "image_width": width,
            "image_height": height,
            "image_dpi": dpi_str,
            "ocr_model": "PaddleOCR 3.x",
            "language": "en",
            "start_timestamp": file_start_ts,
            "end_timestamp": datetime.now().isoformat(),
            "total_runtime_s": file_total_runtime,
            "avg_runtime_per_page_s": avg_runtime_per_page,
            "pdf_load_time_s": round(pdf_load_time, 3),
            "ocr_inference_time_s": round(inference_time, 3),
            "text_serialization_time_s": round(text_serialize_time, 3),
            "json_serialization_time_s": round(json_serialize_time, 3),
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

        # Print Formatted Progress
        print("------------------------------------------------------")
        print(f"Processing {idx} / {total_files}")
        print(f"File         {file_path.name}")
        print(f"Pages        {page_count}")
        print(f"OCR Model    PaddleOCR 3.x")
        print(f"Elapsed      {file_total_runtime} seconds")
        print(f"Average/Page {avg_runtime_per_page} seconds")
        print(f"Peak RAM     {int(resource_stats['peak_ram_mb'])} MB")
        print(f"CPU Avg      {int(resource_stats['avg_cpu_pct'])}%")
        print(f"Status       {status}")
        print("------------------------------------------------------")

    overall_resource_stats = overall_monitor.stop()
    total_benchmark_time = round(time.perf_counter() - benchmark_start_time, 2)

    avg_file_runtime = round(total_benchmark_time / max(1, total_files), 2)
    avg_page_runtime = round(total_benchmark_time / max(1, total_pages_count), 2)

    pages_per_sec = round(total_pages_count / max(0.001, total_benchmark_time), 2)
    files_per_min = round((total_files / max(0.001, total_benchmark_time)) * 60.0, 2)

    # Identify fastest / slowest / largest / smallest files
    successful_records = [r for r in per_file_metrics if r["status"] == "SUCCESS"]
    fastest_file = min(successful_records, key=lambda r: r["total_runtime_s"]) if successful_records else None
    slowest_file = max(successful_records, key=lambda r: r["total_runtime_s"]) if successful_records else None
    largest_file = max(per_file_metrics, key=lambda r: r["file_size_kb"]) if per_file_metrics else None
    smallest_file = min(per_file_metrics, key=lambda r: r["file_size_kb"]) if per_file_metrics else None
    avg_file_size_kb = round(sum(r["file_size_kb"] for r in per_file_metrics) / max(1, total_files), 2)

    sys_info = get_system_environment_info()

    # Step 5: Save Benchmark Reports
    save_benchmark_csv(per_file_metrics)
    save_benchmark_json(sys_info, per_file_metrics, overall_resource_stats, total_benchmark_time)
    save_benchmark_markdown(
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
    )

    # Step 6: Print Final Summary
    print("\n======================================================")
    print("OCR Benchmark Complete")
    print(f"Files Processed   {total_files}")
    print(f"PDFs              {pdf_count}")
    print(f"Images            {image_count}")
    print(f"Pages             {total_pages_count}")
    print(f"Successful        {successful_runs}")
    print(f"Failed            {failed_runs}")
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
    print(f"OCR Model         PaddleOCR 3.x")
    print(f"Output Folder     {OUTPUT_DIR.resolve()}")
    print("======================================================\n")

    logger.info("OCR Benchmark completed successfully.")
    return 0


def save_benchmark_csv(records: List[Dict[str, Any]]) -> Path:
    """Save detailed per-file benchmark results to CSV."""
    csv_path = BENCHMARK_OUTPUT_DIR / "benchmark_results.csv"
    if not records:
        return csv_path

    fieldnames = list(records[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return csv_path


def save_benchmark_json(
    sys_info: Dict[str, str],
    records: List[Dict[str, Any]],
    resource_stats: Dict[str, float],
    total_runtime: float,
) -> Path:
    """Save benchmark metrics export to JSON."""
    json_path = BENCHMARK_OUTPUT_DIR / "benchmark_results.json"
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
) -> Path:
    """Save comprehensive benchmark summary markdown report."""
    md_path = BENCHMARK_OUTPUT_DIR / "benchmark_summary.md"

    md_content = f"""# OCR System Benchmark Report

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
| **Largest File** | {largest_file['filename'] if largest_file else 'N/A'} ({largest_file['file_size_kb'] if largest_file else 0} KB) |
| **Smallest File** | {smallest_file['filename'] if smallest_file else 'N/A'} ({smallest_file['file_size_kb'] if smallest_file else 0} KB) |
| **Average File Size** | {avg_file_size_kb} KB |

---

## 3. Detailed Per-File Benchmark Breakdown

| # | Filename | Type | Pages | Size (KB) | Total (s) | Avg/Page (s) | Peak RAM (MB) | Accuracy % | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    for r in records:
        acc_str = f"{r['accuracy_percent']}%" if r['accuracy_percent'] != "N/A" else "N/A"
        md_content += f"| {r['index']} | {r['filename']} | {r['file_extension']} | {r['page_count']} | {r['file_size_kb']} | {r['total_runtime_s']} | {r['avg_runtime_per_page_s']} | {int(r['peak_ram_mb'])} | {acc_str} | {r['status']} |\n"

    md_content += "\n---\n\n## 4. Warnings & Failures\n\n"
    failures = [r for r in records if r["status"] != "SUCCESS"]
    if failures:
        for f in failures:
            md_content += f"- **{f['filename']}**: {f['error_message']}\n"
    else:
        md_content += "No execution failures or exceptions detected during benchmarking.\n"

    md_path.write_text(md_content, encoding="utf-8")
    return md_path


if __name__ == "__main__":
    sys.exit(run_benchmark())
