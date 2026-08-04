"""Metrics calculation and resource monitoring utilities for OCR benchmarking."""

import os
import time
import threading
from typing import Dict, List, Optional, Tuple
import psutil


def levenshtein_distance(seq1: List[str] | str, seq2: List[str] | str) -> int:
    """Compute Levenshtein edit distance between two sequences or strings."""
    size_x = len(seq1) + 1
    size_y = len(seq2) + 1
    matrix = [[0] * size_y for _ in range(size_x)]
    
    for x in range(size_x):
        matrix[x][0] = x
    for y in range(size_y):
        matrix[0][y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if seq1[x - 1] == seq2[y - 1]:
                matrix[x][y] = matrix[x - 1][y - 1]
            else:
                matrix[x][y] = min(
                    matrix[x - 1][y] + 1,      # Deletion
                    matrix[x][y - 1] + 1,      # Insertion
                    matrix[x - 1][y - 1] + 1,  # Substitution
                )
    return matrix[size_x - 1][size_y - 1]


def compute_ocr_accuracy_metrics(ground_truth_text: str, ocr_text: str) -> Dict[str, float]:
    """Compute Character Error Rate (CER), Word Error Rate (WER), Accuracy %, Precision, Recall, and F1."""
    gt_clean = ground_truth_text.strip()
    ocr_clean = ocr_text.strip()

    if not gt_clean:
        return {
            "cer": 0.0,
            "wer": 0.0,
            "accuracy_percent": 100.0,
            "precision": 1.0,
            "recall": 1.0,
            "f1_score": 1.0,
        }

    # Character Error Rate (CER)
    char_dist = levenshtein_distance(gt_clean, ocr_clean)
    cer = min(1.0, char_dist / max(1, len(gt_clean)))
    accuracy_percent = round(max(0.0, (1.0 - cer) * 100.0), 2)

    # Word Error Rate (WER)
    gt_words = gt_clean.split()
    ocr_words = ocr_clean.split()
    word_dist = levenshtein_distance(gt_words, ocr_words)
    wer = min(1.0, word_dist / max(1, len(gt_words)))

    # Word-level Precision, Recall, and F1 Score
    gt_word_set = set(gt_words)
    ocr_word_set = set(ocr_words)

    true_positives = len(gt_word_set.intersection(ocr_word_set))
    precision = true_positives / len(ocr_word_set) if ocr_word_set else 0.0
    recall = true_positives / len(gt_word_set) if gt_word_set else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "cer": round(cer, 4),
        "wer": round(wer, 4),
        "accuracy_percent": accuracy_percent,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
    }


class ResourceMonitor:
    """Background sampling monitor for tracking RAM and CPU utilization using psutil."""

    def __init__(self, interval_seconds: float = 0.1) -> None:
        self.interval = interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.ram_samples_mb: List[float] = []
        self.cpu_samples_pct: List[float] = []

        self.process = psutil.Process(os.getpid())
        self.start_ram_mb: float = 0.0
        self.end_ram_mb: float = 0.0

    def start(self) -> None:
        """Start tracking process resource consumption."""
        self.ram_samples_mb.clear()
        self.cpu_samples_pct.clear()
        self.start_ram_mb = self.process.memory_info().rss / (1024 * 1024)
        
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def _sample_loop(self) -> None:
        while self._running:
            try:
                ram = self.process.memory_info().rss / (1024 * 1024)
                cpu = self.process.cpu_percent(interval=None)
                self.ram_samples_mb.append(ram)
                self.cpu_samples_pct.append(cpu)
            except Exception:
                pass
            time.sleep(self.interval)

    def stop(self) -> Dict[str, float]:
        """Stop tracking and compute peak/avg resource stats."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

        self.end_ram_mb = self.process.memory_info().rss / (1024 * 1024)

        peak_ram = max(self.ram_samples_mb) if self.ram_samples_mb else self.end_ram_mb
        avg_ram = sum(self.ram_samples_mb) / len(self.ram_samples_mb) if self.ram_samples_mb else self.end_ram_mb

        peak_cpu = max(self.cpu_samples_pct) if self.cpu_samples_pct else 0.0
        avg_cpu = sum(self.cpu_samples_pct) / len(self.cpu_samples_pct) if self.cpu_samples_pct else 0.0

        return {
            "start_ram_mb": round(self.start_ram_mb, 2),
            "end_ram_mb": round(self.end_ram_mb, 2),
            "peak_ram_mb": round(peak_ram, 2),
            "avg_ram_mb": round(avg_ram, 2),
            "peak_cpu_pct": round(peak_cpu, 2),
            "avg_cpu_pct": round(avg_cpu, 2),
        }
