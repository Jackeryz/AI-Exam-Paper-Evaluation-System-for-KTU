# OCR Sandbox

This folder is an isolated experimentation workspace for OCR-related work.

## Scope
- Keep OCR experiments separate from the main backend and frontend.
- Store sample inputs, outputs, and evaluation notes here.
- Use placeholder scripts as a starting point for future implementation.

## Suggested Workflow
1. Place sample files under input/.
2. Run a prototype OCR script from this folder.
3. Save structured output under output/.
4. Compare results against files in ground_truth/.
5. Visualize results via the visualization helpers.

## Offline PaddleOCR Setup
The OCR sandbox is configured to use locally stored PaddleOCR model directories under [models/paddleocr](../../models/paddleocr).

Install its isolated runtime dependencies from the project root:

```bash
python -m pip install -r experiments/ocr_sandbox/requirements.txt
```

- The project intentionally uses local models instead of automatic downloads.
- The sandbox now targets PaddleOCR 3.x and initializes with the 3.x `text_detection_model_dir` and `text_recognition_model_dir` arguments.
- The installed models are the official `PP-OCRv5_mobile_det` detector and
  English-only `en_PP-OCRv5_mobile_rec` recognizer. Run
  `python download_ppocrv5_models.py` from the project root to install them.
- No classifier directory is required: document-orientation, unwarping, and
  textline-orientation classification are disabled.
- No automatic downloads are required when the detection and recognition model
  folders are already populated.
- This makes the OCR sandbox reproducible and suitable for offline use.
- After the required model files are installed, the sandbox can run without network access.

## Adaptive OCR routing

Run the confidence-routed experiment with:

```bash
python experiments/ocr_sandbox/run_adaptive_ocr.py INPUT_FILE
```

`OCR_CONFIDENCE_THRESHOLD` and `BENCHMARK_MODE` are configured in
`utils/config.py`. The router always selects engines from Paddle confidence;
the optional printed/handwritten/mixed classifier is analysis metadata only.
When confidence is below the threshold, Qwen2.5-VL is lazy-loaded and receives
the same preprocessed page. Use `--benchmark` to force both engines and write
`outputs/comparison.json` plus `outputs/summary.md`. Per-engine results are
stored under `outputs/paddle/`, `outputs/qwen/`, and `outputs/routed/`.
