"""Profile the existing adaptive OCR experiment without changing OCR behavior.

This command intentionally uses the same PDF rendering scale, OpenCV operations,
local PaddleOCR model, and single-engine route as the existing Paddle-only batch.
It writes only profiling artifacts under ``outputs/performance``.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import statistics
import sys
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import cv2
import fitz
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import psutil
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.ocr_sandbox.test_ocr import initialize_ocr, run_ocr
from experiments.ocr_sandbox.utils import config
from experiments.ocr_sandbox.adaptive_ocr.classification import PageStyleClassifier


@dataclass
class PageProfile:
    """Measured execution data for one rendered document page."""

    input_file: str
    page_number: int
    width: int
    height: int
    dpi: int
    render_time_seconds: float
    original_rgb_bytes: int
    preprocessed_width: int = 0
    preprocessed_height: int = 0
    preprocessed_rgb_bytes: int = 0
    encoded_png_bytes: int = 0
    large_image_flag: bool = False
    preprocessing_steps_seconds: dict[str, float] = field(default_factory=dict)
    classification_time_seconds: float = 0.0
    detection_time_seconds: float = 0.0
    recognition_time_seconds: float = 0.0
    angle_classification_time_seconds: float = 0.0
    postprocessing_time_seconds: float = 0.0
    ocr_time_seconds: float = 0.0
    save_json_time_seconds: float = 0.0
    save_log_time_seconds: float = 0.0
    memory_before_mb: float = 0.0
    memory_peak_mb: float = 0.0
    memory_after_mb: float = 0.0
    cpu_percent_average: float = 0.0
    cpu_percent_max: float = 0.0
    process_threads_peak: int = 0
    confidence: float = 0.0
    detected_text_regions: int = 0
    recognition_invocations: int = 0
    average_recognition_time_per_region_seconds: float = 0.0
    longest_recognition_call_seconds: float = 0.0
    shortest_recognition_call_seconds: float = 0.0
    total_time_seconds: float = 0.0


class ProcessSampler:
    """Sample process-tree CPU, RSS, and thread count while profiling runs."""

    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid())
        self.samples: list[dict[str, float]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def start(self) -> None:
        """Start non-invasive background sampling."""
        self._thread.start()

    def stop(self) -> None:
        """Stop sampling and wait briefly for the sampling thread."""
        self._stop.set()
        self._thread.join()

    def _sample(self) -> None:
        for process in self._process_tree():
            process.cpu_percent(None)
        while not self._stop.wait(config.PROFILE_CPU_SAMPLE_INTERVAL_SECONDS):
            processes = self._process_tree()
            self.samples.append(
                {
                    "cpu_percent": sum(process.cpu_percent(None) for process in processes),
                    "rss_mb": sum(process.memory_info().rss for process in processes)
                    / (1024 * 1024),
                    "threads": sum(process.num_threads() for process in processes),
                }
            )

    def _process_tree(self) -> list[psutil.Process]:
        try:
            return [self.process, *self.process.children(recursive=True)]
        except psutil.Error:
            return [self.process]


class InstrumentedPreprocessor:
    """Execute the unchanged OpenCV preprocessing operations with timings."""

    def process(self, image: Image.Image) -> tuple[Image.Image, dict[str, float]]:
        """Return the same preprocessed RGB image and each operation's duration."""
        timings: dict[str, float] = {}
        if not config.PREPROCESSING_ENABLED:
            return image.convert("RGB"), {"preprocessing_disabled": 0.0}

        started_at = perf_counter()
        rgb_image = np.array(image.convert("RGB"))
        timings["rgb_conversion"] = perf_counter() - started_at
        started_at = perf_counter()
        gray_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
        timings["grayscale"] = perf_counter() - started_at
        started_at = perf_counter()
        denoised_image = cv2.fastNlMeansDenoising(
            gray_image,
            None,
            config.PREPROCESSING_DENOISE_STRENGTH,
            config.PREPROCESSING_CONTRAST_GRID_SIZE,
            config.PREPROCESSING_CONTRAST_GRID_SIZE,
        )
        timings["noise_removal"] = perf_counter() - started_at
        started_at = perf_counter()
        clahe = cv2.createCLAHE(
            clipLimit=config.PREPROCESSING_CONTRAST_CLIP_LIMIT,
            tileGridSize=(
                config.PREPROCESSING_CONTRAST_GRID_SIZE,
                config.PREPROCESSING_CONTRAST_GRID_SIZE,
            ),
        )
        enhanced_image = clahe.apply(denoised_image)
        timings["local_contrast"] = perf_counter() - started_at
        started_at = perf_counter()
        result = Image.fromarray(cv2.cvtColor(enhanced_image, cv2.COLOR_GRAY2RGB))
        timings["rgb_output"] = perf_counter() - started_at
        return result, timings


class PaddleStageTimer:
    """Temporarily time Paddle detection and recognition predictor calls."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.timings: defaultdict[str, float] = defaultdict(float)
        self.calls: defaultdict[str, int] = defaultdict(int)
        self.call_durations: defaultdict[str, list[float]] = defaultdict(list)
        self._originals: list[tuple[Any, Callable[..., Any]]] = []

    def __enter__(self) -> "PaddleStageTimer":
        pipeline = self.engine.paddlex_pipeline
        self._wrap(pipeline.text_det_model, "detection")
        self._wrap(pipeline.text_rec_model, "recognition")
        return self

    def __exit__(self, *args: Any) -> None:
        for predictor, original_process in self._originals:
            predictor.process = original_process

    def _wrap(self, predictor: Any, stage_name: str) -> None:
        original_process = predictor.process
        self._originals.append((predictor, original_process))

        def timed_process(*args: Any, **kwargs: Any) -> Any:
            started_at = perf_counter()
            try:
                return original_process(*args, **kwargs)
            finally:
                duration = perf_counter() - started_at
                self.timings[stage_name] += duration
                self.calls[stage_name] += 1
                self.call_durations[stage_name].append(duration)

        predictor.process = timed_process


def render_document(input_path: Path) -> list[tuple[PageProfile, Image.Image]]:
    """Render PDF/image inputs exactly as the existing sandbox does, with timing."""
    if input_path.suffix.lower() != ".pdf":
        started_at = perf_counter()
        image = Image.open(input_path).convert("RGB")
        render_time = perf_counter() - started_at
        profile = PageProfile(
            input_file=str(input_path),
            page_number=1,
            width=image.width,
            height=image.height,
            dpi=0,
            render_time_seconds=render_time,
            original_rgb_bytes=image.width * image.height * len(image.getbands()),
        )
        return [(profile, image)]

    rendered: list[tuple[PageProfile, Image.Image]] = []
    document = fitz.open(input_path)
    dpi = int(72 * config.PROFILE_PDF_RENDER_SCALE)
    for page_index, page in enumerate(document):
        started_at = perf_counter()
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(
                config.PROFILE_PDF_RENDER_SCALE, config.PROFILE_PDF_RENDER_SCALE
            )
        )
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        render_time = perf_counter() - started_at
        rendered.append(
            (
                PageProfile(
                    input_file=str(input_path),
                    page_number=page_index + 1,
                    width=image.width,
                    height=image.height,
                    dpi=dpi,
                    render_time_seconds=render_time,
                    original_rgb_bytes=image.width * image.height * len(image.getbands()),
                ),
                image,
            )
        )
    document.close()
    return rendered


def memory_mb() -> float:
    """Return the resident memory of this Python process tree."""
    process = psutil.Process(os.getpid())
    return sum(
        item.memory_info().rss
        for item in [process, *process.children(recursive=True)]
    ) / (1024 * 1024)


def save_profile_result(output_dir: Path, profile: PageProfile, result: dict[str, Any]) -> float:
    """Measure a profiler-only JSON write; existing OCR outputs are never touched."""
    destination = output_dir / f"{Path(profile.input_file).stem}_page_{profile.page_number}.json"
    started_at = perf_counter()
    destination.write_text(
        json.dumps({"profile": asdict(profile), "ocr_result": result}, indent=2),
        encoding="utf-8",
    )
    return perf_counter() - started_at


def profile_inputs(input_paths: list[Path], output_dir: Path) -> dict[str, Any]:
    """Profile initialization and all pages sequentially using the existing engine."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = [item for input_path in input_paths for item in render_document(input_path)]
    initialization_started_at = perf_counter()
    engine = initialize_ocr()
    initialization_time = perf_counter() - initialization_started_at
    preprocessor = InstrumentedPreprocessor()
    classifier = PageStyleClassifier()
    sampler = ProcessSampler()
    sampler.start()
    profiled_pages: list[PageProfile] = []
    function_profiler = cProfile.Profile()
    function_profiler.enable()
    for page_profile, image in pages:
        page_started_at = perf_counter()
        sample_start = len(sampler.samples)
        page_profile.memory_before_mb = memory_mb()
        prepared_image, preprocessing_timings = preprocessor.process(image)
        page_profile.preprocessing_steps_seconds = preprocessing_timings
        classification_started_at = perf_counter()
        if config.ENABLE_IMAGE_CLASSIFICATION:
            classifier.classify(prepared_image)
        page_profile.classification_time_seconds = perf_counter() - classification_started_at
        page_profile.preprocessed_width = prepared_image.width
        page_profile.preprocessed_height = prepared_image.height
        page_profile.preprocessed_rgb_bytes = (
            prepared_image.width * prepared_image.height * len(prepared_image.getbands())
        )
        encoded_image = io.BytesIO()
        prepared_image.save(encoded_image, format="PNG")
        page_profile.encoded_png_bytes = encoded_image.tell()
        page_profile.large_image_flag = (
            page_profile.encoded_png_bytes >= config.PROFILE_LARGE_IMAGE_BYTES
        )
        ocr_started_at = perf_counter()
        with PaddleStageTimer(engine) as stage_timer:
            result = run_ocr(engine, prepared_image)
        page_profile.ocr_time_seconds = perf_counter() - ocr_started_at
        page_profile.detection_time_seconds = stage_timer.timings["detection"]
        page_profile.recognition_time_seconds = stage_timer.timings["recognition"]
        page_profile.detected_text_regions = len(result["bounding_boxes"])
        page_profile.recognition_invocations = stage_timer.calls["recognition"]
        recognition_durations = stage_timer.call_durations["recognition"]
        if page_profile.detected_text_regions:
            page_profile.average_recognition_time_per_region_seconds = (
                page_profile.recognition_time_seconds
                / page_profile.detected_text_regions
            )
        if recognition_durations:
            page_profile.longest_recognition_call_seconds = max(recognition_durations)
            page_profile.shortest_recognition_call_seconds = min(recognition_durations)
        page_profile.postprocessing_time_seconds = max(
            page_profile.ocr_time_seconds
            - page_profile.detection_time_seconds
            - page_profile.recognition_time_seconds,
            0.0,
        )
        page_profile.confidence = float(result["confidence"])
        page_samples = sampler.samples[sample_start:]
        page_profile.memory_peak_mb = max(
            [page_profile.memory_before_mb, *[sample["rss_mb"] for sample in page_samples]]
        )
        page_profile.memory_after_mb = memory_mb()
        page_profile.save_json_time_seconds = save_profile_result(output_dir, page_profile, result)
        log_started_at = perf_counter()
        with (output_dir / "profiling.log").open("a", encoding="utf-8") as log_file:
            log_file.write(
                f"{page_profile.input_file} page={page_profile.page_number} "
                f"ocr={page_profile.ocr_time_seconds:.3f}\n"
            )
        page_profile.save_log_time_seconds = perf_counter() - log_started_at
        page_profile.total_time_seconds = (
            page_profile.render_time_seconds + perf_counter() - page_started_at
        )
        page_profile.cpu_percent_average = statistics.mean(
            sample["cpu_percent"] for sample in page_samples
        ) if page_samples else 0.0
        page_profile.cpu_percent_max = max(
            (sample["cpu_percent"] for sample in page_samples), default=0.0
        )
        page_profile.process_threads_peak = int(max(
            (sample["threads"] for sample in page_samples), default=0
        ))
        profiled_pages.append(page_profile)
    function_profiler.disable()
    sampler.stop()
    top_functions = _top_functions(function_profiler)
    cpu_samples = sampler.samples or [{"cpu_percent": 0.0, "threads": 0.0, "rss_mb": memory_mb()}]
    data = {
        "model_initialization": {
            "time_seconds": initialization_time,
            "load_count": 1,
            "loaded_once_for_all_pages": True,
            "angle_classification_enabled": False,
            "paddle_cpu_num_environment": os.environ.get("CPU_NUM"),
        },
        "execution": {
            "page_processing_mode": "sequential",
            "rendering_library": "PyMuPDF (fitz)",
            "render_scale": config.PROFILE_PDF_RENDER_SCALE,
            "cpu_count_logical": psutil.cpu_count(),
            "cpu_samples": cpu_samples,
            "top_functions": top_functions,
        },
        "pages": [asdict(page) for page in profiled_pages],
    }
    return data


def _top_functions(profiler: cProfile.Profile) -> list[dict[str, Any]]:
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    rows: list[dict[str, Any]] = []
    for (filename, line_number, function_name), values in sorted(
        stats.stats.items(), key=lambda item: item[1][3], reverse=True
    )[:10]:
        rows.append(
            {
                "function": f"{Path(filename).name}:{line_number}({function_name})",
                "calls": values[1],
                "total_time_seconds": round(values[3], 6),
            }
        )
    return rows


def write_reports(data: dict[str, Any], output_dir: Path) -> None:
    """Write machine-readable metrics, Markdown report, and requested PNG charts."""
    pages = data["pages"]
    total_runtime = data["model_initialization"]["time_seconds"] + sum(
        page["total_time_seconds"] for page in pages
    )
    totals = {
        "PDF rendering": sum(page["render_time_seconds"] for page in pages),
        "Preprocessing": sum(sum(page["preprocessing_steps_seconds"].values()) for page in pages),
        "Classification metadata": sum(page["classification_time_seconds"] for page in pages),
        "OCR detection": sum(page["detection_time_seconds"] for page in pages),
        "OCR recognition": sum(page["recognition_time_seconds"] for page in pages),
        "Saving": sum(page["save_json_time_seconds"] + page["save_log_time_seconds"] for page in pages),
    }
    totals["Other"] = max(total_runtime - sum(totals.values()), 0.0)
    data["summary"] = {
        "total_runtime_seconds": total_runtime,
        "average_page_runtime_seconds": statistics.mean(page["total_time_seconds"] for page in pages),
        "median_page_runtime_seconds": statistics.median(page["total_time_seconds"] for page in pages),
        "slowest_page": max(pages, key=lambda page: page["total_time_seconds"]),
        "fastest_page": min(pages, key=lambda page: page["total_time_seconds"]),
        "stage_totals_seconds": totals,
    }
    start_memory = pages[0]["memory_before_mb"]
    final_memory = pages[-1]["memory_after_mb"]
    data["memory_analysis"] = {
        "start_mb": start_memory,
        "final_mb": final_memory,
        "peak_mb": max(page["memory_peak_mb"] for page in pages),
        "growth_mb": final_memory - start_memory,
        "leak_detected": final_memory - start_memory >= config.PROFILE_MEMORY_LEAK_GROWTH_MB,
    }
    report_io: dict[str, float] = {
        "json_seconds": 0.0,
        "markdown_seconds": 0.0,
        "charts_seconds": 0.0,
        "annotated_images_seconds": 0.0,
        "benchmark_reports_seconds": 0.0,
    }
    chart_started_at = perf_counter()
    _write_charts(totals, pages, output_dir)
    report_io["charts_seconds"] = perf_counter() - chart_started_at
    data["report_io"] = report_io
    markdown_started_at = perf_counter()
    (output_dir / "performance_report.md").write_text(
        _markdown_report(data), encoding="utf-8"
    )
    report_io["markdown_seconds"] = perf_counter() - markdown_started_at
    json_started_at = perf_counter()
    (output_dir / "performance.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    report_io["json_seconds"] = perf_counter() - json_started_at
    (output_dir / "performance.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_region_analysis(data: dict[str, Any], output_dir: Path) -> None:
    """Write per-page region/recognition timing analysis from measured calls."""
    pages = data["pages"]
    lines = [
        "# Recognition Region Analysis",
        "",
        "This report uses the existing PaddleOCR run. A recognition invocation is "
        "one call to PaddleX's recognition predictor; it can process one or more "
        "detected text regions.",
        "",
        "| Page | Detected regions | Recognition invocations | Recognition time (s) | Avg / region (s) | Longest call (s) | Shortest call (s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for page in pages:
        lines.append(
            f"| {Path(page['input_file']).name} p{page['page_number']} | "
            f"{page['detected_text_regions']} | {page['recognition_invocations']} | "
            f"{page['recognition_time_seconds']:.3f} | "
            f"{page['average_recognition_time_per_region_seconds']:.3f} | "
            f"{page['longest_recognition_call_seconds']:.3f} | "
            f"{page['shortest_recognition_call_seconds']:.3f} |"
        )
    regions = [page["detected_text_regions"] for page in pages]
    average_per_region = [
        page["average_recognition_time_per_region_seconds"]
        for page in pages
        if page["detected_text_regions"]
    ]
    slowest = max(pages, key=lambda page: page["recognition_time_seconds"])
    most_regions = max(pages, key=lambda page: page["detected_text_regions"])
    lines.extend([
        "",
        "## Interpretation",
        f"- Total detected regions: {sum(regions)}.",
        f"- Average regions per page: {statistics.mean(regions):.2f}.",
        f"- Average recognition time per region: {statistics.mean(average_per_region):.3f}s.",
        f"- Slowest recognition page: {Path(slowest['input_file']).name} p{slowest['page_number']} ({slowest['recognition_time_seconds']:.3f}s across {slowest['detected_text_regions']} regions).",
        f"- Most text regions: {Path(most_regions['input_file']).name} p{most_regions['page_number']} ({most_regions['detected_text_regions']} regions).",
        "- Compare the slowest recognition page with the highest-region page and average-per-region column to distinguish region volume from unusually expensive recognition calls.",
    ])
    (output_dir / "region_analysis.md").write_text("\n".join(lines), encoding="utf-8")


def _write_charts(totals: dict[str, float], pages: list[dict[str, Any]], output_dir: Path) -> None:
    plt.figure(figsize=(10, 6))
    plt.pie(totals.values(), labels=totals.keys(), autopct="%1.1f%%")
    plt.title("Adaptive OCR Runtime Breakdown")
    plt.tight_layout()
    plt.savefig(output_dir / "runtime_breakdown.png", dpi=150)
    plt.close()
    labels = [f"{Path(page['input_file']).stem} p{page['page_number']}" for page in pages]
    plt.figure(figsize=(12, 6))
    plt.bar(range(len(pages)), [page["total_time_seconds"] for page in pages])
    plt.xticks(range(len(pages)), labels, rotation=45, ha="right")
    plt.ylabel("Seconds")
    plt.title("Runtime per Page")
    plt.tight_layout()
    plt.savefig(output_dir / "page_runtime.png", dpi=150)
    plt.close()


def _markdown_report(data: dict[str, Any]) -> str:
    summary = data["summary"]
    pages = data["pages"]
    init = data["model_initialization"]
    lines = [
        "# Adaptive OCR Performance Report",
        "",
        "## Overall results",
        f"- Total runtime: {summary['total_runtime_seconds']:.2f}s",
        f"- Average page runtime: {summary['average_page_runtime_seconds']:.2f}s",
        f"- Median page runtime: {summary['median_page_runtime_seconds']:.2f}s",
        f"- Slowest page: {Path(summary['slowest_page']['input_file']).name} page {summary['slowest_page']['page_number']} ({summary['slowest_page']['total_time_seconds']:.2f}s)",
        f"- Fastest page: {Path(summary['fastest_page']['input_file']).name} page {summary['fastest_page']['page_number']} ({summary['fastest_page']['total_time_seconds']:.2f}s)",
        "",
        "## PaddleOCR initialization",
        f"- Model loads: {init['load_count']}; loaded once for all pages: {init['loaded_once_for_all_pages']}",
        f"- Initialization time: {init['time_seconds']:.2f}s",
        f"- Angle classification enabled: {init['angle_classification_enabled']}",
        f"- Configured CPU_NUM: {init['paddle_cpu_num_environment']}",
        "",
        "## PDF rendering and image resolution",
        "| Page | Resolution | DPI | Render time (s) | RGB MB | PNG MB | Large image |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for page in pages:
        lines.append(
            f"| {Path(page['input_file']).name} p{page['page_number']} | {page['width']}×{page['height']} | {page['dpi']} | {page['render_time_seconds']:.3f} | {page['original_rgb_bytes'] / (1024 * 1024):.2f} | {page['encoded_png_bytes'] / (1024 * 1024):.2f} | {page['large_image_flag']} |"
        )
    lines.extend([
        "",
        "## Per-page pipeline breakdown",
        "| Page | Render | Preprocess | Classify | Detection | Recognition | Postprocess | Saving | Total |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for page in pages:
        lines.append(
            f"| {Path(page['input_file']).name} p{page['page_number']} | {page['render_time_seconds']:.3f} | {sum(page['preprocessing_steps_seconds'].values()):.3f} | {page['classification_time_seconds']:.3f} | {page['detection_time_seconds']:.3f} | {page['recognition_time_seconds']:.3f} | {page['postprocessing_time_seconds']:.3f} | {page['save_json_time_seconds'] + page['save_log_time_seconds']:.3f} | {page['total_time_seconds']:.3f} |"
        )
    lines.extend(["", "## Preprocessing steps", "| Step | Total seconds |", "|---|---:|"])
    preprocessing_totals: defaultdict[str, float] = defaultdict(float)
    for page in pages:
        for name, duration in page["preprocessing_steps_seconds"].items():
            preprocessing_totals[name] += duration
    lines.extend(f"| {name} | {duration:.3f} |" for name, duration in preprocessing_totals.items())
    lines.extend(["", "## CPU and memory"])
    cpu_samples = data["execution"]["cpu_samples"]
    ideal_parallelism_bound = sum(page["total_time_seconds"] for page in pages) / max(
        page["total_time_seconds"] for page in pages
    )
    memory = data["memory_analysis"]
    lines.extend([
        f"- Average CPU: {statistics.mean(sample['cpu_percent'] for sample in cpu_samples):.2f}%",
        f"- Maximum CPU: {max(sample['cpu_percent'] for sample in cpu_samples):.2f}%",
        f"- Peak process threads: {max(sample['threads'] for sample in cpu_samples):.0f}",
        f"- Peak sampled RSS: {max(sample['rss_mb'] for sample in cpu_samples):.2f} MB",
        f"- Page execution is sequential. Workload-based page-level parallelism upper bound: {ideal_parallelism_bound:.2f}x, before CPU/RAM/model contention.",
        "- PaddleOCR is configured with `CPU_NUM=1`; sampled thread count is recorded per page in `performance.json`.",
        f"- Memory: start {memory['start_mb']:.2f} MB, peak {memory['peak_mb']:.2f} MB, final {memory['final_mb']:.2f} MB. Leak detected: {memory['leak_detected']}.",
        "",
        "## Disk I/O",
        f"- Per-page profiling JSON writes: {sum(page['save_json_time_seconds'] for page in pages):.3f}s",
        f"- Per-page profiling log writes: {sum(page['save_log_time_seconds'] for page in pages):.3f}s",
        f"- Markdown report write: {data['report_io']['markdown_seconds']:.3f}s",
        f"- Chart writes: {data['report_io']['charts_seconds']:.3f}s",
        "- Annotated images and benchmark reports: not produced by this Paddle-only profiling run (0.000s).",
        "",
        "## Top 10 slowest profiled functions",
        "| Function | Calls | Cumulative seconds |",
        "|---|---:|---:|",
    ])
    lines.extend(
        f"| {item['function']} | {item['calls']} | {item['total_time_seconds']:.3f} |"
        for item in data["execution"]["top_functions"]
    )
    lines.extend(["", "## Performance summary"])
    bottlenecks = list(summary["stage_totals_seconds"].items()) + [
        ("PaddleOCR initialization", data["model_initialization"]["time_seconds"]),
        ("Noise removal", preprocessing_totals.get("noise_removal", 0.0)),
        ("Local contrast", preprocessing_totals.get("local_contrast", 0.0)),
    ]
    advice = {
        "PaddleOCR initialization": ("Model construction and local-weight loading", "Keep a long-lived singleton", "Low", "Low"),
        "PDF rendering": ("PyMuPDF rasterizes pages at 144 DPI", "Evaluate lower render DPI in a separate experiment", "Low", "Medium"),
        "Preprocessing": ("OpenCV transformations run on every rendered pixel", "Compare each operation in a separate accuracy-controlled experiment", "Low", "Medium"),
        "Noise removal": ("Non-local means denoising is computationally intensive", "Compare denoising settings separately", "Medium", "Medium"),
        "Local contrast": ("CLAHE processes every pixel", "Compare CLAHE settings separately", "Low", "Low"),
        "OCR detection": ("Detection runs over each full rendered page", "Evaluate resolution and execution-provider options separately", "Medium", "High"),
        "OCR recognition": ("Recognition runs for every detected text region", "Evaluate batching and hardware execution separately", "Medium", "High"),
        "Saving": ("Artifacts are serialized for every page", "Evaluate deferred artifact writes separately", "Low", "Low"),
        "Other": ("Residual time includes orchestration and native work", "Add narrower probes after reviewing this report", "Low", "Low"),
        "Classification metadata": ("Optional metadata analysis runs independently of routing", "Evaluate whether metadata is required", "Low", "Low"),
    }
    ranked: dict[str, float] = {}
    for name, duration in bottlenecks:
        ranked[name] = max(ranked.get(name, 0.0), duration)
    for index, (stage, duration) in enumerate(
        sorted(ranked.items(), key=lambda item: item[1], reverse=True)[:10], start=1
    ):
        why, suggestion, difficulty, risk = advice.get(
            stage, ("Measured runtime concentration", "Investigate separately", "Unknown", "Unknown")
        )
        impact = duration / summary["total_runtime_seconds"] * 100
        lines.extend([
            f"### #{index} {stage}",
            f"- Current time: {duration:.2f}s ({impact:.1f}% of measured total)",
            f"- Why it is slow: {why}.",
            f"- Suggested optimization: {suggestion}.",
            f"- Estimated speedup: theoretical upper bound is recovering {impact:.1f}% of total runtime; validate separately.",
            f"- Difficulty: {difficulty}.",
            f"- Risk: {risk}.",
            "",
        ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse one or more existing PDF/image inputs to profile."""
    parser = argparse.ArgumentParser(description="Profile the adaptive OCR experiment")
    parser.add_argument("input_files", nargs="+", type=Path)
    return parser.parse_args()


def main() -> int:
    """Run instrumentation and write profiling artifacts without OCR changes."""
    args = parse_args()
    paths = [path.expanduser().resolve() for path in args.input_files]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        print(f"Missing inputs: {', '.join(missing)}", file=sys.stderr)
        return 1
    output_dir = Path(__file__).resolve().parent / config.ADAPTIVE_OUTPUT_DIR / config.PROFILE_OUTPUT_DIR
    data = profile_inputs(paths, output_dir)
    write_reports(data, output_dir)
    write_region_analysis(data, output_dir)
    print(f"Performance report -> {output_dir / 'performance_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
