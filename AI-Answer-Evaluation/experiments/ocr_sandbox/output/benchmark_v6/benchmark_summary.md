# PP-OCRV6 System Benchmark Report

**Execution Date**: 2026-08-16 14:09:48

---

## 1. System Environment

| Metric | Details |
| :--- | :--- |
| **Operating System** | Windows 10 (10.0.26200) |
| **CPU Architecture** | Intel64 Family 6 Model 140 Stepping 1, GenuineIntel (4 Cores) |
| **Installed RAM** | 7.75 GB |
| **Python Version** | 3.11.4 |
| **OCR Model** | PP-OCRv6 (small_det + small_rec) |
| **Language** | English (en) |
| **Cold Start Time** | 16.132 s |

---

## 2. Benchmark Summary Metrics

| Metric | Benchmark Result |
| :--- | :--- |
| **Total Files Processed** | 15 (PDFs: 4, Images: 11) |
| **Total Pages Processed** | 24 |
| **Successful Runs** | 15 |
| **Failed Runs** | 0 |
| **Total Pipeline Runtime** | 778.37 seconds |
| **Average Runtime per File** | 51.89 seconds |
| **Average Runtime per Page** | 32.43 seconds |
| **OCR Throughput** | **0.031 pages/sec** (1.16 files/min) |
| **Peak RAM Consumption** | 1100.16 MB |
| **Average RAM Consumption** | 351.8 MB |
| **Peak CPU Utilization** | 232.7% |
| **Average CPU Utilization** | 168.4% |
| **Fastest File** | sample_test.png (0.635s) |
| **Slowest File** | 2303.13931v1.pdf (346.558s) |

---

## 3. Detailed Per-File Benchmark Breakdown

| # | Filename | Type | Pages | Size (KB) | Total (s) | Avg/Page (s) | Avg Conf | Accuracy % | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 1000131266 - Jackson Tom Joseph.jpg | .jpg | 1 | 3697.25 | 53.81 | 53.81 | 0.9417 | N/A | SUCCESS |
| 2 | 1000131267 - Jackson Tom Joseph.jpg | .jpg | 1 | 3885.95 | 64.522 | 64.522 | 0.953 | N/A | SUCCESS |
| 3 | 20260803_182105 - Pes United Gamer.jpg | .jpg | 1 | 7177.64 | 60.315 | 60.315 | 0.6605 | N/A | SUCCESS |
| 4 | 20260803_182158 - Pes United Gamer.jpg | .jpg | 1 | 8178.51 | 37.679 | 37.679 | 0.6222 | N/A | SUCCESS |
| 5 | DocScanner Aug 6, 2026 6-19 PM - Gouri Sreekumar.pdf | .pdf | 2 | 933.39 | 14.577 | 7.288 | 0.8329 | N/A | SUCCESS |
| 6 | IMG-20260804-WA0035 - Krishnendu P B.jpg | .jpg | 1 | 52.46 | 6.594 | 6.594 | 0.9288 | N/A | SUCCESS |
| 7 | IMG-20260804-WA0036 - Krishnendu P B.jpg | .jpg | 1 | 64.58 | 5.727 | 5.727 | 0.9373 | N/A | SUCCESS |
| 8 | IMG-20260804-WA0041 - Krishnendu P B.jpg | .jpg | 1 | 474.72 | 21.588 | 21.588 | 0.9114 | N/A | SUCCESS |
| 9 | IMG_20251023_060747 - Swarag Antony.jpg | .jpg | 1 | 1793.88 | 30.671 | 30.671 | 0.8017 | N/A | SUCCESS |
| 10 | IMG_20251023_060811 - Swarag Antony.jpg | .jpg | 1 | 1171.33 | 23.856 | 23.856 | 0.8954 | N/A | SUCCESS |
| 11 | IMG_20260129_204523 - Krishnendu P B.jpg | .jpg | 1 | 1893.71 | 32.645 | 32.645 | 0.8028 | N/A | SUCCESS |
| 12 | Screenshot 26-Jul-26 6_59_51 PM.pdf | .pdf | 2 | 109.21 | 15.719 | 7.859 | 0.8872 | N/A | SUCCESS |
| 13 | 2303.13931v1.pdf | .pdf | 8 | 416.28 | 346.558 | 43.32 | 0.9882 | N/A | SUCCESS |
| 14 | ocr_verification_sample.pdf | .pdf | 1 | 150.66 | 46.606 | 46.606 | 0.9895 | N/A | SUCCESS |
| 15 | sample_test.png | .png | 1 | 2.38 | 0.635 | 0.635 | 0.9994 | N/A | SUCCESS |
