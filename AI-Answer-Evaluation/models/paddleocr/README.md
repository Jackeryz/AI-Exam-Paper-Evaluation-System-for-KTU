# Local PaddleOCR Models

This folder stores PaddleOCR model artifacts locally so the OCR sandbox can run without downloading models automatically.

## Required folders

- `det/` for the detection model
- `rec/` for the recognition model

## Expected files

Each folder should contain the PaddleOCR 3.x inference files:

```text
det/
    inference.json
    inference.pdiparams
    inference.yml

rec/
    inference.json
    inference.pdiparams
    inference.yml

```

## Download guidance

Install the official Hugging Face models with
`python experiments/ocr_sandbox/download_ppocrv5_models.py`.

- Detection model: `PaddlePaddle/PP-OCRv5_mobile_det`
- English recognition model: `PaddlePaddle/en_PP-OCRv5_mobile_rec`

The OCR sandbox disables document orientation classification, document
unwarping, and textline orientation. Consequently, no `cls/` folder is
required.
