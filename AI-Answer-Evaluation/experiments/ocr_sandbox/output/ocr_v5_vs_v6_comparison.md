# PP-OCRv5 vs PP-OCRv6 Performance & Quality Comparison

**Execution Date**: 2026-08-16
**Environment**: Windows 10 | Python 3.11.4 | PaddlePaddle 3.3.1 | PaddleOCR 3.7.0

---

## 1. Summary Comparison Table

| Metric | PP-OCRv5 | PP-OCRv6 | Difference / Delta |
|---|---:|---:|---:|
| **Files** | 15 | 15 | 0 |
| **Pages** | 24 | 24 | 0 |
| **Total Runtime** | 1029.6 s | 761.5 s | **268.1 s faster (1.35x Speedup)** |
| **Avg Runtime / Page** | 42.9 s | 31.73 s | **11.17 s faster** |
| **Estimated Recognition Time** | 719.24 s | 531.35 s | **1.35x Faster Recognition** |
| **Pages / Second Throughput** | 0.023 | 0.032 | **+0.009 pages/sec** |
| **Peak RAM Consumption** | 967 MB | 1100 MB | +132 MB |
| **Average CPU %** | 178% | 168% | -10% |
| **Average Confidence Score** | 0.7726 | 0.8768 | 0.1042 |
| **Character Error Rate (CER)** | N/A — no ground truth available | N/A — no ground truth available | N/A |
| **Word Error Rate (WER)** | N/A — no ground truth available | N/A — no ground truth available | N/A |

---

## 2. Performance Conclusion

- **Faster Model**: **PP-OCRv6**
- **Overall Speedup**: **1.35x**
- **Runtime Reduction**: **26.0%**
- **Recognition Speed Improvement**: **1.35x faster recognition**
- **Memory Difference**: PP-OCRv5 consumes **132 MB less peak RAM** (967 MB vs 1100 MB).

---

## 3. Accuracy Conclusion

- **Ground Truth Status**: **Not Available -- Ground truth files not provided in ground_truth/**
- **Notice**: Accuracy (CER / WER / Precision / Recall / F1) cannot yet be established from the current benchmark because no ground truth reference text files exist in `experiments/ocr_sandbox/ground_truth/`. The benchmark measures performance, runtime, throughput, and model recognition confidence.

---

## 4. Recommendation

Option 3: Both PP-OCRv5 and PP-OCRv6 should remain available for further testing.

- PP-OCRv6 provides a **1.35x speedup** (26.0% overall runtime reduction) and faster per-page inference (31.73s vs 42.9s).
- PP-OCRv5 requires **less peak RAM** (967 MB vs 1100 MB).
- Accuracy (CER/WER) remains unestablished due to absence of ground truth files in `experiments/ocr_sandbox/ground_truth/`.
- Recommendation: Maintain PP-OCRv5 as default baseline while keeping PP-OCRv6 accessible as an isolated high-throughput configuration.

---

## 5. Fairness Check

- **Input Dataset**: Identical 15 files (4 PDFs, 11 Images, 24 total pages).
- **Machine & Hardware**: Windows 10 x64, CPU single-thread execution (`CPU_NUM=1`).
- **Python & Paddle Environment**: Python 3.11.4, PaddlePaddle 3.3.1, PaddleOCR 3.7.0.
- **Rendering & Preprocessing**: Identical PyMuPDF rendering matrix (2x2) and PIL RGB image processing.

---

## 6. File-by-File Detailed Breakdown

| Filename | Pages | V5 Runtime (s) | V6 Runtime (s) | Speedup | Reduction % | V5 Peak RAM | V6 Peak RAM |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1000131266 - Jackson Tom Joseph.jpg | 1 | 39.469 | 53.81 | 0.73x | -36.3% | 927 MB | 1100 MB |
| 1000131267 - Jackson Tom Joseph.jpg | 1 | 34.651 | 64.522 | 0.54x | -86.2% | 738 MB | 768 MB |
| 20260803_182105 - Pes United Gamer.jpg | 1 | 41.468 | 60.315 | 0.69x | -45.4% | 967 MB | 1009 MB |
| 20260803_182158 - Pes United Gamer.jpg | 1 | 39.369 | 37.679 | 1.04x | 4.3% | 966 MB | 993 MB |
| 2303.13931v1.pdf | 8 | 644.551 | 346.558 | 1.86x | 46.2% | 305 MB | 582 MB |
| DocScanner Aug 6, 2026 6-19 PM - Gouri Sreekumar.pdf | 2 | 19.13 | 14.577 | 1.31x | 23.8% | 246 MB | 295 MB |
| IMG-20260804-WA0035 - Krishnendu P B.jpg | 1 | 8.926 | 6.594 | 1.35x | 26.1% | 200 MB | 245 MB |
| IMG-20260804-WA0036 - Krishnendu P B.jpg | 1 | 9.928 | 5.727 | 1.73x | 42.3% | 200 MB | 252 MB |
| IMG-20260804-WA0041 - Krishnendu P B.jpg | 1 | 26.29 | 21.588 | 1.22x | 17.9% | 522 MB | 586 MB |
| IMG_20251023_060747 - Swarag Antony.jpg | 1 | 29.172 | 30.671 | 0.95x | -5.1% | 747 MB | 804 MB |
| IMG_20251023_060811 - Swarag Antony.jpg | 1 | 19.03 | 23.856 | 0.8x | -25.4% | 570 MB | 600 MB |
| IMG_20260129_204523 - Krishnendu P B.jpg | 1 | 24.526 | 32.645 | 0.75x | -33.1% | 647 MB | 778 MB |
| Screenshot 26-Jul-26 6_59_51 PM.pdf | 2 | 19.813 | 15.719 | 1.26x | 20.7% | 239 MB | 291 MB |
| ocr_verification_sample.pdf | 1 | 72.817 | 46.606 | 1.56x | 36.0% | 255 MB | 607 MB |
| sample_test.png | 1 | 0.46 | 0.635 | 0.72x | -38.0% | 179 MB | 286 MB |
