# PaddleOCR 3.x migration notes

This migration is limited to the isolated OCR sandbox and the model storage layout. No backend, frontend, RAG, grading, or embedding logic was changed.

## What changed

- Updated the OCR sandbox in [experiments/ocr_sandbox/test_ocr.py](experiments/ocr_sandbox/test_ocr.py) to use PaddleOCR 3.x initialization arguments.
- Switched from older `det_model_dir` / `rec_model_dir` style assumptions to the PaddleOCR 3.x local-model arguments:
  - `text_detection_model_dir`
  - `text_recognition_model_dir`
- Kept the sandbox offline-first by validating the local directories under [models/paddleocr](models/paddleocr) before initialization.
- Added a regression test at [experiments/ocr_sandbox/tests/test_test_ocr.py](experiments/ocr_sandbox/tests/test_test_ocr.py) to guard the 3.x initialization path.
- Added PaddleOCR 3.x package pins to [backend/requirements.txt](backend/requirements.txt).

## Local model layout

The sandbox expects the following folders to exist and contain model files:

- [models/paddleocr/det](models/paddleocr/det)
- [models/paddleocr/rec](models/paddleocr/rec)
- [models/paddleocr/cls](models/paddleocr/cls)

## Installation notes

Install the OCR runtime with:

```bash
pip install -r backend/requirements.txt
```

## Verification

The regression test can be run with:

```bash
pytest -q experiments/ocr_sandbox/tests/test_test_ocr.py
```
