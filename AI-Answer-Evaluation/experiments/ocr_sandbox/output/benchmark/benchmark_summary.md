# PP-OCRV5 System Benchmark Report

**Execution Date**: 2026-08-16 13:56:40

---

## 1. System Environment

| Metric | Details |
| :--- | :--- |
| **Operating System** | Windows 10 (10.0.26200) |
| **CPU Architecture** | Intel64 Family 6 Model 140 Stepping 1, GenuineIntel (4 Cores) |
| **Installed RAM** | 7.75 GB |
| **Python Version** | 3.11.4 |
| **OCR Model** | PaddleOCR 3.x (PP-OCRv5_mobile_det + en_PP-OCRv5_mobile_rec) |
| **Language** | English (en) |
| **Cold Start Time** | 7.876 s |

---

## 2. Benchmark Summary Metrics

| Metric | Benchmark Result |
| :--- | :--- |
| **Total Files Processed** | 15 (PDFs: 4, Images: 11) |
| **Total Pages Processed** | 24 |
| **Successful Runs** | 15 |
| **Failed Runs** | 0 |
| **Total Pipeline Runtime** | 1038.54 seconds |
| **Average Runtime per File** | 69.24 seconds |
| **Average Runtime per Page** | 43.27 seconds |
| **OCR Throughput** | **0.023 pages/sec** (0.87 files/min) |
| **Peak RAM Consumption** | 967.68 MB |
| **Average RAM Consumption** | 242.7 MB |
| **Peak CPU Utilization** | 299.2% |
| **Average CPU Utilization** | 178.86% |
| **Fastest File** | sample_test.png (0.46s) |
| **Slowest File** | 2303.13931v1.pdf (644.551s) |

---

## 3. Detailed Per-File Benchmark Breakdown

| # | Filename | Type | Pages | Size (KB) | Total (s) | Avg/Page (s) | Avg Conf | Accuracy % | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 1000131266 - Jackson Tom Joseph.jpg | .jpg | 1 | 3697.25 | 39.469 | 39.469 | 0.7611 | N/A | SUCCESS |
| 2 | 1000131267 - Jackson Tom Joseph.jpg | .jpg | 1 | 3885.95 | 34.651 | 34.651 | 0.5958 | N/A | SUCCESS |
| 3 | 20260803_182105 - Pes United Gamer.jpg | .jpg | 1 | 7177.64 | 41.468 | 41.468 | 0.5982 | N/A | SUCCESS |
| 4 | 20260803_182158 - Pes United Gamer.jpg | .jpg | 1 | 8178.51 | 39.369 | 39.369 | 0.5601 | N/A | SUCCESS |
| 5 | DocScanner Aug 6, 2026 6-19 PM - Gouri Sreekumar.pdf | .pdf | 2 | 933.39 | 19.13 | 9.565 | 0.6818 | N/A | SUCCESS |
| 6 | IMG-20260804-WA0035 - Krishnendu P B.jpg | .jpg | 1 | 52.46 | 8.926 | 8.926 | 0.9133 | N/A | SUCCESS |
| 7 | IMG-20260804-WA0036 - Krishnendu P B.jpg | .jpg | 1 | 64.58 | 9.928 | 9.928 | 0.9044 | N/A | SUCCESS |
| 8 | IMG-20260804-WA0041 - Krishnendu P B.jpg | .jpg | 1 | 474.72 | 26.29 | 26.29 | 0.8051 | N/A | SUCCESS |
| 9 | IMG_20251023_060747 - Swarag Antony.jpg | .jpg | 1 | 1793.88 | 29.172 | 29.172 | 0.5615 | N/A | SUCCESS |
| 10 | IMG_20251023_060811 - Swarag Antony.jpg | .jpg | 1 | 1171.33 | 19.03 | 19.03 | 0.7686 | N/A | SUCCESS |
| 11 | IMG_20260129_204523 - Krishnendu P B.jpg | .jpg | 1 | 1893.71 | 24.526 | 24.526 | 0.6763 | N/A | SUCCESS |
| 12 | Screenshot 26-Jul-26 6_59_51 PM.pdf | .pdf | 2 | 109.21 | 19.813 | 9.906 | 0.8322 | N/A | SUCCESS |
| 13 | 2303.13931v1.pdf | .pdf | 8 | 416.28 | 644.551 | 80.569 | 0.9792 | N/A | SUCCESS |
| 14 | ocr_verification_sample.pdf | .pdf | 1 | 150.66 | 72.817 | 72.817 | 0.955 | N/A | SUCCESS |
| 15 | sample_test.png | .png | 1 | 2.38 | 0.46 | 0.46 | 0.9971 | N/A | SUCCESS |
