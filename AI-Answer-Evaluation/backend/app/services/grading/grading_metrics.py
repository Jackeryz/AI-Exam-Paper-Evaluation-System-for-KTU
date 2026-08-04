"""Centralized, reusable quantitative metrics for answer paper grading."""

import re
from typing import Dict, List, Optional, Set
import numpy as np


class GradingMetrics:
    """Pure mathematical and text-based metrics for deterministic answer evaluation."""

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two embedding vectors (0.0 to 1.0)."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        v1 = np.array(vec1, dtype=float)
        v2 = np.array(vec2, dtype=float)
        dot = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 > 0 and norm2 > 0:
            sim = dot / (norm1 * norm2)
            return float(np.clip(sim, 0.0, 1.0))
        return 0.0

    @staticmethod
    def keyword_coverage(
        student_text: str,
        required_keywords: List[str],
        synonyms: Optional[Dict[str, List[str]]] = None,
    ) -> float:
        """Compute proportion of required keywords or their synonyms present in student answer."""
        if not required_keywords:
            return 1.0
        if not student_text.strip():
            return 0.0

        lowered_text = student_text.lower()
        matched = 0

        syn_map = synonyms or {}

        for kw in required_keywords:
            kw_lower = kw.lower()
            # Direct keyword match
            if kw_lower in lowered_text:
                matched += 1
                continue
            
            # Check synonyms if available
            syn_list = syn_map.get(kw, syn_map.get(kw_lower, []))
            if any(syn.lower() in lowered_text for syn in syn_list):
                matched += 1

        return float(round(matched / len(required_keywords), 4))

    @staticmethod
    def concept_overlap(student_text: str, required_concepts: List[str]) -> float:
        """Compute coverage ratio of core conceptual phrases."""
        if not required_concepts:
            return 1.0
        if not student_text.strip():
            return 0.0

        lowered_text = student_text.lower()
        matched = sum(1 for concept in required_concepts if concept.lower() in lowered_text)
        return float(round(matched / len(required_concepts), 4))

    @staticmethod
    def length_normalization(student_text: str, ideal_text: str) -> float:
        """Ratio of student answer length relative to ideal answer, penalized if under 30% or over 250%."""
        student_words = len(student_text.split())
        ideal_words = len(ideal_text.split())
        if ideal_words == 0:
            return 1.0
        if student_words == 0:
            return 0.0

        ratio = student_words / ideal_words
        if ratio < 0.30:
            # Severely incomplete answer
            return float(round(ratio / 0.30, 4))
        elif ratio <= 1.5:
            return 1.0
        else:
            # Overly verbose / bloated penalty
            penalty = max(0.5, 1.0 - (ratio - 1.5) * 0.2)
            return float(round(penalty, 4))

    @staticmethod
    def section_coverage_ratio(student_text: str, expected_sections: List[str]) -> float:
        """Check if expected structural sections (e.g. Definition, Advantages, Applications) exist."""
        if not expected_sections:
            return 1.0
        lowered_text = student_text.lower()
        found = sum(1 for section in expected_sections if section.lower() in lowered_text)
        return float(round(found / len(expected_sections), 4))
