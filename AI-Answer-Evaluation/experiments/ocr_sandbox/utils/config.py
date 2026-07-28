"""Configuration values for the isolated OCR sandbox experiments."""

INPUT_DIR = "input"
OUTPUT_DIR = "output"
GROUND_TRUTH_DIR = "ground_truth"
VISUALIZE_DIR = "visualize"

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".tiff"}

# Routing and benchmarking.  Keep tuning values here so the pipeline does not
# embed environment-specific thresholds or model settings in implementation code.
OCR_CONFIDENCE_THRESHOLD = 0.90
BENCHMARK_MODE = False
ENABLE_IMAGE_CLASSIFICATION = True

# Pre-processing parameters.
PREPROCESSING_ENABLED = True
PREPROCESSING_DENOISE_STRENGTH = 7
PREPROCESSING_CONTRAST_CLIP_LIMIT = 2.0
PREPROCESSING_CONTRAST_GRID_SIZE = 8
CLASSIFIER_CANNY_LOW_THRESHOLD = 50
CLASSIFIER_CANNY_HIGH_THRESHOLD = 150
CLASSIFIER_HORIZONTAL_KERNEL_WIDTH = 25
CLASSIFIER_PRINTED_LINE_DENSITY = 0.20
CLASSIFIER_PRINTED_EDGE_DENSITY = 0.03
CLASSIFIER_HANDWRITTEN_LINE_DENSITY = 0.08

# Qwen2.5-VL is loaded only when the router falls back or benchmark mode is on.
QWEN_MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
QWEN_MAX_NEW_TOKENS = 2048
QWEN_PROMPT = "Transcribe all visible text exactly. Preserve reading order and line breaks."
QWEN_DEVICE_PREFERENCE = "auto"

# New adaptive outputs intentionally live separately from legacy `output/`.
ADAPTIVE_OUTPUT_DIR = "outputs"
ROUTER_LOG_FILENAME = "ocr_router.log"

# Profiling only; these values do not alter OCR execution.
PROFILE_OUTPUT_DIR = "performance"
PROFILE_PDF_RENDER_SCALE = 2
PROFILE_CPU_SAMPLE_INTERVAL_SECONDS = 0.2
PROFILE_LARGE_IMAGE_BYTES = 8 * 1024 * 1024
PROFILE_MEMORY_LEAK_GROWTH_MB = 32
