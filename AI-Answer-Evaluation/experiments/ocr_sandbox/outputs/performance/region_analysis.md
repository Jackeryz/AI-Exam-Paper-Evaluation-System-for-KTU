# Recognition Region Analysis

This report uses the existing PaddleOCR run. A recognition invocation is one call to PaddleX's recognition predictor; it can process one or more detected text regions.

| Page | Detected regions | Recognition invocations | Recognition time (s) | Avg / region (s) | Longest call (s) | Shortest call (s) |
|---|---:|---:|---:|---:|---:|---:|
| 2303.13931v1.pdf p1 | 80 | 14 | 84.261 | 1.053 | 11.219 | 1.622 |
| 2303.13931v1.pdf p2 | 110 | 19 | 100.791 | 0.916 | 6.861 | 1.550 |
| 2303.13931v1.pdf p3 | 111 | 19 | 101.923 | 0.918 | 7.184 | 1.600 |
| 2303.13931v1.pdf p4 | 115 | 20 | 90.535 | 0.787 | 14.372 | 1.497 |
| 2303.13931v1.pdf p5 | 120 | 20 | 98.054 | 0.817 | 7.400 | 1.507 |
| 2303.13931v1.pdf p6 | 102 | 17 | 92.501 | 0.907 | 7.191 | 1.545 |
| 2303.13931v1.pdf p7 | 155 | 26 | 80.174 | 0.517 | 9.092 | 1.469 |
| 2303.13931v1.pdf p8 | 154 | 26 | 162.858 | 1.058 | 10.173 | 4.256 |
| ocr_verification_sample.pdf p1 | 80 | 14 | 84.387 | 1.055 | 11.516 | 1.548 |
| Screenshot 26-Jul-26 6_59_51 PM.pdf p1 | 11 | 2 | 7.525 | 0.684 | 3.877 | 3.649 |
| Screenshot 26-Jul-26 6_59_51 PM.pdf p2 | 21 | 4 | 12.341 | 0.588 | 4.050 | 2.404 |

## Interpretation
- Total detected regions: 1059.
- Average regions per page: 96.27.
- Average recognition time per region: 0.845s.
- Slowest recognition page: 2303.13931v1.pdf p8 (162.858s across 154 regions).
- Most text regions: 2303.13931v1.pdf p7 (155 regions).
- Compare the slowest recognition page with the highest-region page and average-per-region column to distinguish region volume from unusually expensive recognition calls.