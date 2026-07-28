# Adaptive OCR Performance Report

## Overall results
- Total runtime: 996.53s
- Average page runtime: 88.81s
- Median page runtime: 95.45s
- Slowest page: 2303.13931v1.pdf page 8 (174.02s)
- Fastest page: Screenshot 26-Jul-26 6_59_51 PM.pdf page 1 (12.29s)

## PaddleOCR initialization
- Model loads: 1; loaded once for all pages: True
- Initialization time: 19.60s
- Angle classification enabled: False
- Configured CPU_NUM: 1

## PDF rendering and image resolution
| Page | Resolution | DPI | Render time (s) | RGB MB | PNG MB | Large image |
|---|---:|---:|---:|---:|---:|---|
| 2303.13931v1.pdf p1 | 1191×1684 | 144 | 0.064 | 5.74 | 0.53 | False |
| 2303.13931v1.pdf p2 | 1191×1684 | 144 | 0.017 | 5.74 | 0.64 | False |
| 2303.13931v1.pdf p3 | 1191×1684 | 144 | 0.016 | 5.74 | 0.62 | False |
| 2303.13931v1.pdf p4 | 1191×1684 | 144 | 0.052 | 5.74 | 0.49 | False |
| 2303.13931v1.pdf p5 | 1191×1684 | 144 | 0.014 | 5.74 | 0.61 | False |
| 2303.13931v1.pdf p6 | 1191×1684 | 144 | 0.020 | 5.74 | 0.57 | False |
| 2303.13931v1.pdf p7 | 1191×1684 | 144 | 0.017 | 5.74 | 0.44 | False |
| 2303.13931v1.pdf p8 | 1191×1684 | 144 | 0.022 | 5.74 | 0.68 | False |
| ocr_verification_sample.pdf p1 | 1191×1684 | 144 | 0.029 | 5.74 | 0.53 | False |
| Screenshot 26-Jul-26 6_59_51 PM.pdf p1 | 1190×1684 | 144 | 0.052 | 5.73 | 0.53 | False |
| Screenshot 26-Jul-26 6_59_51 PM.pdf p2 | 1190×1684 | 144 | 0.053 | 5.73 | 0.81 | False |

## Per-page pipeline breakdown
| Page | Render | Preprocess | Classify | Detection | Recognition | Postprocess | Saving | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2303.13931v1.pdf p1 | 0.064 | 0.475 | 0.048 | 4.881 | 84.261 | 0.087 | 0.039 | 90.190 |
| 2303.13931v1.pdf p2 | 0.017 | 0.467 | 0.026 | 4.164 | 100.791 | 0.087 | 0.018 | 105.820 |
| 2303.13931v1.pdf p3 | 0.016 | 0.446 | 0.019 | 4.230 | 101.923 | 0.096 | 0.048 | 106.938 |
| 2303.13931v1.pdf p4 | 0.052 | 0.465 | 0.027 | 4.134 | 90.535 | 0.097 | 0.018 | 95.454 |
| 2303.13931v1.pdf p5 | 0.014 | 0.444 | 0.023 | 4.064 | 98.054 | 0.129 | 0.016 | 102.917 |
| 2303.13931v1.pdf p6 | 0.020 | 0.420 | 0.023 | 4.545 | 92.501 | 0.088 | 0.021 | 97.780 |
| 2303.13931v1.pdf p7 | 0.017 | 0.431 | 0.019 | 4.086 | 80.174 | 0.097 | 0.073 | 85.046 |
| 2303.13931v1.pdf p8 | 0.022 | 1.044 | 0.101 | 9.321 | 162.858 | 0.252 | 0.030 | 174.017 |
| ocr_verification_sample.pdf p1 | 0.029 | 0.433 | 0.025 | 4.164 | 84.387 | 0.073 | 0.015 | 89.252 |
| Screenshot 26-Jul-26 6_59_51 PM.pdf p1 | 0.052 | 0.440 | 0.019 | 3.957 | 7.525 | 0.027 | 0.008 | 12.293 |
| Screenshot 26-Jul-26 6_59_51 PM.pdf p2 | 0.053 | 0.486 | 0.018 | 4.001 | 12.341 | 0.054 | 0.004 | 17.223 |

## Preprocessing steps
| Step | Total seconds |
|---|---:|
| rgb_conversion | 0.211 |
| grayscale | 0.043 |
| noise_removal | 5.107 |
| local_contrast | 0.097 |
| rgb_output | 0.092 |

## CPU and memory
- Average CPU: 173.84%
- Maximum CPU: 356.70%
- Peak process threads: 23
- Peak sampled RSS: 792.39 MB
- Page execution is sequential. Workload-based page-level parallelism upper bound: 5.61x, before CPU/RAM/model contention.
- PaddleOCR is configured with `CPU_NUM=1`; sampled thread count is recorded per page in `performance.json`.
- Memory: start 679.87 MB, peak 792.39 MB, final 468.34 MB. Leak detected: False.

## Disk I/O
- Per-page profiling JSON writes: 0.274s
- Per-page profiling log writes: 0.014s
- Markdown report write: 0.000s
- Chart writes: 1.017s
- Annotated images and benchmark reports: not produced by this Paddle-only profiling run (0.000s).

## Top 10 slowest profiled functions
| Function | Calls | Cumulative seconds |
|---|---:|---:|
| test_ocr.py:125(run_ocr) | 11 | 967.971 |
| ocr.py:208(predict) | 11 | 967.786 |
| _parallel.py:148(predict) | 22 | 967.786 |
| pipeline.py:292(predict) | 22 | 967.774 |
| base_predictor.py:61(__call__) | 1092 | 967.037 |
| base_predictor.py:119(apply) | 1092 | 967.036 |
| profile_adaptive_ocr.py:186(timed_process) | 192 | 966.897 |
| runner.py:289(__call__) | 192 | 963.160 |
| runner.py:261(__call__) | 192 | 962.923 |
| ~:0(<built-in method paddle.base.libpaddle.run>) | 192 | 959.901 |

## Performance summary
### #1 OCR recognition
- Current time: 915.35s (91.9% of measured total)
- Why it is slow: Recognition runs for every detected text region.
- Suggested optimization: Evaluate batching and hardware execution separately.
- Estimated speedup: theoretical upper bound is recovering 91.9% of total runtime; validate separately.
- Difficulty: Medium.
- Risk: High.

### #2 OCR detection
- Current time: 51.55s (5.2% of measured total)
- Why it is slow: Detection runs over each full rendered page.
- Suggested optimization: Evaluate resolution and execution-provider options separately.
- Estimated speedup: theoretical upper bound is recovering 5.2% of total runtime; validate separately.
- Difficulty: Medium.
- Risk: High.

### #3 Other
- Current time: 23.09s (2.3% of measured total)
- Why it is slow: Residual time includes orchestration and native work.
- Suggested optimization: Add narrower probes after reviewing this report.
- Estimated speedup: theoretical upper bound is recovering 2.3% of total runtime; validate separately.
- Difficulty: Low.
- Risk: Low.

### #4 PaddleOCR initialization
- Current time: 19.60s (2.0% of measured total)
- Why it is slow: Model construction and local-weight loading.
- Suggested optimization: Keep a long-lived singleton.
- Estimated speedup: theoretical upper bound is recovering 2.0% of total runtime; validate separately.
- Difficulty: Low.
- Risk: Low.

### #5 Preprocessing
- Current time: 5.55s (0.6% of measured total)
- Why it is slow: OpenCV transformations run on every rendered pixel.
- Suggested optimization: Compare each operation in a separate accuracy-controlled experiment.
- Estimated speedup: theoretical upper bound is recovering 0.6% of total runtime; validate separately.
- Difficulty: Low.
- Risk: Medium.

### #6 Noise removal
- Current time: 5.11s (0.5% of measured total)
- Why it is slow: Non-local means denoising is computationally intensive.
- Suggested optimization: Compare denoising settings separately.
- Estimated speedup: theoretical upper bound is recovering 0.5% of total runtime; validate separately.
- Difficulty: Medium.
- Risk: Medium.

### #7 PDF rendering
- Current time: 0.36s (0.0% of measured total)
- Why it is slow: PyMuPDF rasterizes pages at 144 DPI.
- Suggested optimization: Evaluate lower render DPI in a separate experiment.
- Estimated speedup: theoretical upper bound is recovering 0.0% of total runtime; validate separately.
- Difficulty: Low.
- Risk: Medium.

### #8 Classification metadata
- Current time: 0.35s (0.0% of measured total)
- Why it is slow: Optional metadata analysis runs independently of routing.
- Suggested optimization: Evaluate whether metadata is required.
- Estimated speedup: theoretical upper bound is recovering 0.0% of total runtime; validate separately.
- Difficulty: Low.
- Risk: Low.

### #9 Saving
- Current time: 0.29s (0.0% of measured total)
- Why it is slow: Artifacts are serialized for every page.
- Suggested optimization: Evaluate deferred artifact writes separately.
- Estimated speedup: theoretical upper bound is recovering 0.0% of total runtime; validate separately.
- Difficulty: Low.
- Risk: Low.

### #10 Local contrast
- Current time: 0.10s (0.0% of measured total)
- Why it is slow: CLAHE processes every pixel.
- Suggested optimization: Compare CLAHE settings separately.
- Estimated speedup: theoretical upper bound is recovering 0.0% of total runtime; validate separately.
- Difficulty: Low.
- Risk: Low.
