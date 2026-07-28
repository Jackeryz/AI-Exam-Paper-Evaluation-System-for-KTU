"""OpenCV image preprocessing shared by all OCR strategies."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from experiments.ocr_sandbox.utils import config


class OpenCVPreprocessor:
    """Apply conservative denoising and local-contrast enhancement to a page."""

    def process(self, image: Image.Image) -> Image.Image:
        """Return an RGB image suitable for both PaddleOCR and Qwen2.5-VL."""
        if not config.PREPROCESSING_ENABLED:
            return image.convert("RGB")

        rgb_image = np.array(image.convert("RGB"))
        gray_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
        denoised_image = cv2.fastNlMeansDenoising(
            gray_image,
            None,
            config.PREPROCESSING_DENOISE_STRENGTH,
            config.PREPROCESSING_CONTRAST_GRID_SIZE,
            config.PREPROCESSING_CONTRAST_GRID_SIZE,
        )
        clahe = cv2.createCLAHE(
            clipLimit=config.PREPROCESSING_CONTRAST_CLIP_LIMIT,
            tileGridSize=(
                config.PREPROCESSING_CONTRAST_GRID_SIZE,
                config.PREPROCESSING_CONTRAST_GRID_SIZE,
            ),
        )
        enhanced_image = clahe.apply(denoised_image)
        return Image.fromarray(cv2.cvtColor(enhanced_image, cv2.COLOR_GRAY2RGB))
