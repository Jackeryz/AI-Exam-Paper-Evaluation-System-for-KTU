"""Install the official PaddleOCR v6 small models into models/paddleocr/v6/."""

import sys
from pathlib import Path
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[2] / "models" / "paddleocr" / "v6"
MODEL_FILES = ("inference.json", "inference.pdiparams", "inference.yml")
MODELS = (
    ("PaddlePaddle/PP-OCRv6_small_det", ROOT / "det"),
    ("PaddlePaddle/PP-OCRv6_small_rec", ROOT / "rec"),
)


def download_v6_models() -> None:
    """Download PP-OCRv6 small detection and recognition model files."""
    print(f"Downloading official PP-OCRv6 small models into {ROOT}...")
    for repo_id, destination in MODELS:
        destination.mkdir(parents=True, exist_ok=True)
        print(f"Installing {repo_id} -> {destination}...")
        for filename in MODEL_FILES:
            path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type="model",
                local_dir=destination,
            )
            print(f"Downloaded {filename} -> {path}")
    print("\nPP-OCRv6 small model files downloaded successfully!")


if __name__ == "__main__":
    download_v6_models()
