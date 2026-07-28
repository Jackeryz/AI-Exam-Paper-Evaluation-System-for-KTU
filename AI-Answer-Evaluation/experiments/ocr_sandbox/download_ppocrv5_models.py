"""Install the official PaddleOCR v5 mobile models used by this sandbox."""

from pathlib import Path

from huggingface_hub import hf_hub_download


ROOT = Path(__file__).resolve().parents[2] / "models" / "paddleocr"
MODEL_FILES = ("inference.json", "inference.pdiparams", "inference.yml")
MODELS = (
    ("PaddlePaddle/PP-OCRv5_mobile_det", ROOT / "det"),
    ("PaddlePaddle/en_PP-OCRv5_mobile_rec", ROOT / "rec"),
)


for repo_id, destination in MODELS:
    destination.mkdir(parents=True, exist_ok=True)
    print(f"Installing {repo_id} into {destination}...")
    for filename in MODEL_FILES:
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="model",
            local_dir=destination,
        )
        print(f"Downloaded {filename} -> {path}")
