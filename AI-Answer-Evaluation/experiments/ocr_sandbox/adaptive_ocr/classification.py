"""Lightweight optional page-style metadata classification."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from experiments.ocr_sandbox.utils import config

from .models import PageClassification


class PageStyleClassifier:
    """Estimate page style for analysis only; it never participates in routing."""

    def classify(self, image: Image.Image) -> PageClassification:
        """Classify a page from simple line-density and connected-component cues."""
        grayscale = np.array(image.convert("L"))
        edges = cv2.Canny(
            grayscale,
            config.CLASSIFIER_CANNY_LOW_THRESHOLD,
            config.CLASSIFIER_CANNY_HIGH_THRESHOLD,
        )
        horizontal = cv2.morphologyEx(
            edges,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(
                cv2.MORPH_RECT, (config.CLASSIFIER_HORIZONTAL_KERNEL_WIDTH, 1)
            ),
        )
        edge_density = float(np.count_nonzero(edges)) / edges.size
        line_density = float(np.count_nonzero(horizontal)) / max(
            np.count_nonzero(edges), 1
        )
        if (
            line_density >= config.CLASSIFIER_PRINTED_LINE_DENSITY
            and edge_density >= config.CLASSIFIER_PRINTED_EDGE_DENSITY
        ):
            return "PRINTED"
        if line_density < config.CLASSIFIER_HANDWRITTEN_LINE_DENSITY:
            return "HANDWRITTEN"
        return "MIXED"
