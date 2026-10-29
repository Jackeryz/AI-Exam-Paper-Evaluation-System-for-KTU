# Task 7 — Evaluation Intelligence, Local LLM Readiness, and Prototype Quality Report

**KTU AI-Assisted Handwritten Answer Evaluation Platform**  
*Evaluation Intelligence & Local LLM Infrastructure Audit*  
**Date:** October 2026  
**Status:** Verification Complete — Zero-Regression Stabilized Prototype

---

## Executive Summary

Task 7 focused on enhancing the scoring intelligence and teacher usability of the KTU AI-Assisted Handwritten Answer Evaluation Platform while rigorously assessing the machine's hardware readiness for local LLM inference.

### Key Achievements:
1. **Hardware & Local LLM Assessment:** Thorough, non-disruptive hardware profiling revealed an **Intel Core i3-1115G4 (2 physical cores, 4 threads, 8.12 GB RAM with ~0.95 GB free, no discrete NVIDIA GPU / CUDA)**. We determined that 7B–8B parameter models (requiring 4.5–6.0 GB RAM) are completely impractical and would destabilize the host system. The only runnable model family is **0.5B–1.5B Small Language Models (SLMs)** (such as `qwen2.5:1.5b-instruct` requiring ~1.0 GB RAM).
2. **Offline Latency & Telemetry Protection:** Implemented an asynchronous fast liveness check and negative cache (0.5s timeout, 15s TTL) in `OllamaProvider`, dropping offline evaluation latency from **~110 seconds down to < 2.0 seconds** while preserving 100% honest telemetry (`DETERMINISTIC_HEURISTIC_FALLBACK` / `DETERMINISTIC_BLANK_INTERCEPT`). Cloud LLM leakage remains strictly blocked (`ALLOW_CLOUD_LLM=False`).
3. **Decoupled Scoring & Evidence Extraction:** Eliminated concept multi-counting across keyword matching, semantic cosine similarity, and qualitative understanding. Replaced uniform global mark scaling with criterion-level assessment (`_evaluate_criterion_deterministically`) which extracts concrete student answer quotes as supporting evidence and enforces mathematical formula, unit, and negation bounds.
4. **Enhanced Contradiction Detection:** Upgraded `GradingMetrics.detect_contradictions` with full reference context (`ideal_answer + question_text + rubric_text`), sentence-scoped negation detection, economic inverse reversals, inverted Ohm's law/power formulas, stack vs. queue LIFO/FIFO inversions, and ACID property validations.
5. **Teacher Usability Enhancements:** Updated the review interface (`EvaluationReview.jsx`) with a **"Supporting Answer Evidence"** column in the Criterion-Wise Breakdown table, enabling teachers to inspect the exact quote credited for each mark deduction/award.
6. **Benchmark Validation & Invariant Integrity:**
   - **Original 22-Case Benchmark (`synthetic_grading_dataset.json`):** Kept strictly unchanged. Mean Absolute Error (MAE) dropped from **2.169 marks (24.16%) down to 0.527 marks (6.00%)**, RMSE dropped from **3.301 to 0.818 marks**, and Exact Agreement doubled to **36.36%** (Agreement within 1.0 mark: **86.36%**).
   - **New 25-Case Versioned Benchmark (`evaluation_benchmark_v2.json`):** Created across 5 KTU courses (CST 201 Data Structures, CST 202 Operating Systems, EST 100 Engineering Mechanics, EST 130 Basics of Electrical Engineering, HUT 300 Industrial Economics & Management). Validated via `run_benchmark_v2.py` with MAE **1.304 marks** and all invariants passing.
7. **Zero Regression:** All **58 backend automated tests** pass cleanly. Frontend production build passes with zero errors (`vite build` in 2.54s).

---

## 1. Local LLM Readiness & Feasibility Analysis

### 1.1 Machine Hardware Profile

| Component | Specification | Operational Status |
| :--- | :--- | :--- |
| **Operating System** | Microsoft Windows 11 Home Single Language (Build 26100) | Normal |
| **CPU** | 11th Gen Intel(R) Core(TM) i3-1115G4 @ 3.00GHz (2 Cores, 4 Logical Processors, AVX-512 capable) | Constrained (Dual-Core) |
| **Total Physical RAM** | 8.12 GB (8,313 MB) | Constrained |
| **Available Free RAM** | ~0.95 GB to 1.12 GB (idle state with IDE and backend services running) | **Severe Bottleneck** |
| **GPU / Acceleration** | Intel(R) UHD Graphics (Integrated, 1 GB shared video memory, **No NVIDIA CUDA / ROCm**) | CPU-only inference required |
| **Available Storage** | Drive C: **29.49 GB free** out of 237.22 GB | Sufficient for small models |
| **Local LLM Engine** | Ollama daemon | **Offline / Not Installed in PATH** |

### 1.2 Model Feasibility & Trade-Off Analysis

| Model Architecture | Parameter Size | Quantization | RAM / VRAM Required | Feasibility on This Machine | Expected Performance & Trade-Offs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Llama-3.1 / 3.2** | 8B | Q4_K_M | ~5.5 GB | ❌ **Completely Impractical** | Severe memory swapping / OS freeze. Total system RAM is 8 GB with only ~1 GB free. |
| **Mistral-Instruct** | 7B | Q4_K_M | ~4.8 GB | ❌ **Completely Impractical** | Exceeds free physical RAM. Would trigger paging thrash and system lockup. |
| **Phi-3-Mini** | 3.8B | Q4_K_M | ~2.6 GB | ⚠️ **Marginal / High Risk** | Requires closing all background apps; high risk of Out-Of-Memory (OOM) kill. |
| **Qwen2.5-Instruct** | **1.5B** | **Q4_K_M** | **~1.1 GB** | ✅ **Feasible with Preparation** | Suitable balance between structured JSON output, rubric adherence, and memory safety. Expected CPU inference speed: ~4–8 tokens/sec. |
| **Qwen2.5-Instruct** | **0.5B** | **Q4_K_M** | **~0.6 GB** | ✅ **Safest Local Option** | Fits comfortably within current 0.95 GB free memory. Fast CPU inference (~12–18 tokens/sec), but weaker JSON schema compliance and nuanced feedback. |

### 1.3 Recommended Local Setup Steps (When Host Deployment is Approved)

1. **Install Ollama for Windows:** Download and install from `https://ollama.com/download/windows`.
2. **Pull the Recommended Small Model:**
   ```powershell
   ollama pull qwen2.5:1.5b-instruct
   ```
3. **Verify Local Inference:**
   ```powershell
   ollama run qwen2.5:1.5b-instruct "State Ohm's Law and its mathematical formula."
   ```
4. **Configure Application Environment:**
   Set in `backend/.env`:
   ```env
   DEFAULT_LLM_PROVIDER=ollama
   OLLAMA_MODEL=qwen2.5:1.5b-instruct
   OLLAMA_BASE_URL=http://localhost:11434
   ALLOW_CLOUD_LLM=False
   ```

### 1.4 Genuine Inference Status & Latency Safeguard

- **Current Status:** Genuine local LLM inference was **tested and verified as offline** because Ollama is not installed on this workstation.
- **Privacy & Telemetry Honesty:** Cloud LLM access remains strictly disabled (`ALLOW_CLOUD_LLM=False`). Every evaluation output honestly displays `evaluation_method: "DETERMINISTIC_HEURISTIC_FALLBACK"` or `"DETERMINISTIC_BLANK_INTERCEPT"`. Fallback results are never disguised as LLM inference.
- **Fast Liveness & Negative Caching:** Added in `backend/app/services/llm/llm_interface.py`:
  - 0.5s HTTP connect timeout for Ollama ping.
  - 15-second negative cache TTL when offline.
  - Result: Prevents repetitive 110s timeouts during multi-question evaluation, reducing fallback execution latency to **< 2.0s**.

---

## 2. Evaluation Weaknesses Discovered and Engine Improvements

### 2.1 Weaknesses in the Previous Scoring Engine

1. **Concept Multi-Counting:** Keyword coverage ratio, semantic cosine similarity, and qualitative understanding were all factored into a global product. A student mentioning keywords without explanation was credited multiple times across metrics.
2. **Uniform Global Mark Scaling:** The previous engine computed a single global ratio (e.g., 0.72) and multiplied every rubric section by that ratio, obscuring which criteria the student actually fulfilled or missed.
3. **Absence of Student Evidence Quotes:** The criterion breakdown gave a generic message (`"Criteria satisfied"`) without quoting the student's actual words.
4. **False Negatives on Meta-Rubrics:** Criteria named `"Definition & Law"`, `"Concept Understanding"`, or `"Statement"` failed when the student stated the principle directly rather than repeating the meta-words `"definition"` or `"concept"`.
5. **False Positives on Inverted Formulas and Reversals:** Inverted formulas (e.g., $I = R/V$, $P = V/I$) or contradicted concepts (e.g., `"Stacks follow FIFO order"`) previously received high semantic similarity scores because MiniLM embeddings measure topical proximity rather than logical correctness.

### 2.2 Improvements Implemented

1. **Structured Criterion-Level Assessment:**
   - Implemented `_evaluate_criterion_deterministically` in `backend/app/services/grading/evaluator.py`.
   - Distinguishes between:
     - **Numerical calculations:** Verifies values and units ($40\text{ W}$, $5\ \Omega$, series vs. parallel formulas).
     - **Mathematical formulas:** Verifies formula syntax ($V=IR$, $P=VI$, $\%\Delta Q / \%\Delta P$) and penalizes inversions ($I=R/V$).
     - **Complexity and operations:** Validates time bounds ($O(1)$ vs. $O(n)$) and stack/queue operations.
     - **Domain-specific concepts:** Extracts domain terms from section names, matching them against student answers and known synonym sets.
     - **Meta-criteria:** Evaluates core concept coverage and cosine similarity when rubric sections use general pedagogical labels (`"Definition"`, `"Understanding"`, `"Completeness"`).
2. **Supporting Evidence Snippet Extraction:**
   - Evaluator extracts the exact sentence from the student's submission that satisfies each criterion and attaches it as `evidence` in `CriterionDeduction`.
3. **Decoupled Semantic Similarity:**
   - Semantic similarity is now used as supporting evidence rather than independent proof of correctness. When factual contradictions or formula errors are present, correctness and criterion marks are penalized regardless of high cosine similarity.
4. **Strict Additive Aggregation:**
   - `ScoreAggregator.aggregate` strictly computes:
     $$\text{Final Marks} \equiv \sum_{i=1}^n \text{Criterion Awarded}_i$$
   - Guarantees complete consistency between the itemized breakdown table and the headline score.
5. **Enhanced Qualitative LLM Schema:**
   - Updated `QualitativeLLMEvaluation` with `CriterionAssessment` schema (`criterion`, `performance_ratio`, `evidence`, `missing_or_incorrect`). When local LLMs are active, structured criterion evaluations are returned directly.

---

## 3. Feedback and Teacher Usability Improvements

### 3.1 Review Interface Enhancements (`EvaluationReview.jsx`)

1. **Supporting Evidence Column:**
   - Added a dedicated column in the Criterion-Wise Breakdown table displaying the exact student sentence or phrase that supported each score award.
   - For missed or contradicted criteria, displays a clear explanation of what was missing.
2. **Clear Feedback Panes:**
   - Distinct, color-coded sections for:
     - **Key Strengths:** Concepts accurately stated.
     - **Identified Weaknesses / Missing Concepts:** Required concepts omitted.
     - **Factual Contradictions / Errors:** Incorrect claims flagged in red.
     - **Improvement Suggestions:** Actionable guidance for student revision.
3. **Audit History & Override Stability:**
   - Confirmed that teacher score overrides, qualitative feedback edits, and approval statuses remain fully preserved across browser reloads, re-evaluations, and multi-format exports (CSV, Excel, PDF).

---

## 4. Benchmark Validation Results

### 4.1 Original 22-Case Benchmark (`synthetic_grading_dataset.json`)

The original 22 test cases were kept completely unchanged to serve as a strict regression test.

| Metric | Task 6 Baseline (Heuristic Fallback) | Task 7 Refined Engine | Absolute Improvement |
| :--- | :--- | :--- | :--- |
| **Total Cases Evaluated** | 22 | 22 | — |
| **Mean Absolute Error (MAE)** | **2.169 marks** (24.16%) | **0.527 marks** (6.00%) | **-1.642 marks (75.7% error reduction)** |
| **Root Mean Squared Error (RMSE)** | **3.301 marks** (35.94%) | **0.818 marks** (8.86%) | **-2.483 marks (75.2% RMSE reduction)** |
| **Exact Agreement Rate** | 18.18% (4/22) | **36.36%** (8/22) | **+18.18% (2x increase)** |
| **Agreement within 0.5 marks** | 31.82% (7/22) | **77.27%** (17/22) | **+45.45%** |
| **Agreement within 1.0 mark** | 40.91% (9/22) | **86.36%** (19/22) | **+45.45%** |
| **Invariants Check** | | | |
| - `marks_within_zero_to_max` | PASS | PASS | Maintained |
| - `blank_answers_receive_zero` | PASS | PASS | Maintained |
| - `irrelevant_content_receives_zero` | PASS | PASS | Maintained |
| - `alternative_terminology_credited`| PASS | PASS | Maintained |
| - `formula_spacing_not_penalized` | PASS | PASS | Maintained |

### 4.2 Benchmark V2 (`evaluation_benchmark_v2.json`)

A new, separate benchmark dataset of **25 distinct cases** across 5 subjects was created and validated:

| Subject Code | Subject Name | Cases Tested | Key Scenarios Tested |
| :--- | :--- | :--- | :--- |
| **CST 201** | Data Structures | V2-01 to V2-05 | Stacks, Queues, LIFO/FIFO, $O(1)$ operations, Linked Lists vs. Arrays |
| **CST 202** | Operating Systems | V2-06 to V2-10 | Preemptive vs. Non-preemptive scheduling, Banker's algorithm, Deadlock conditions, Paging vs. Segmentation |
| **EST 100** | Engineering Mechanics | V2-11 to V2-15 | Lami's Theorem, Friction laws, Truss method of joints, Moment of Inertia |
| **EST 130** | Basics of Electrical Eng. | V2-16 to V2-20 | Kirchhoff's Laws (KCL/KVL), Faraday's Law, Parallel equivalent resistance, Inverted formulas |
| **HUT 300** | Industrial Economics & Mgmt | V2-21 to V2-25 | Price Elasticity of Demand (PED), Inflation types, Balance Sheet equation ($A = L + E$) |

**Benchmark V2 Aggregate Results:**
- **Cases Evaluated:** 25
- **Mean Absolute Error (MAE):** 1.304 marks
- **Root Mean Squared Error (RMSE):** 2.078 marks
- **Exact Agreement Rate:** 12.0% (3/25)
- **Agreement within 0.5 marks:** 52.0% (13/25)
- **Agreement within 1.0 mark:** 64.0% (16/25)
- **All Core Invariants:** **PASS** (Zero marks for blank answers, zero marks for irrelevant content, marks bounded $[0, \text{Max Marks}]$).

---

## 5. Verification Commands and Genuine Outputs

### 5.1 Backend Test Suite Execution
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -v
```
**Output:**
```
================= 58 passed, 16 warnings in 154.43s (0:02:34) =================
```

### 5.2 22-Case Original Benchmark
```powershell
.\.venv\Scripts\python.exe experiments/grading_validation/run_grading_validation.py
```
**Output:**
```
Total Cases Evaluated:       22
Mean Absolute Error (MAE):   0.527 marks (Normalized: 6.00%)
Root Mean Squared Error:     0.818 marks (Normalized: 8.86%)
Exact Agreement Rate:        36.36% (8/22)
Agreement within 0.5 marks:  77.27% (17/22)
Agreement within 1.0 mark:   86.36% (19/22)
Invariants Check:            True
```

### 5.3 25-Case Benchmark V2
```powershell
.\.venv\Scripts\python.exe experiments/grading_validation/run_benchmark_v2.py
```
**Output:**
```
Total Cases Evaluated:       25
Mean Absolute Error (MAE):   1.304 marks
Root Mean Squared Error:     2.078 marks
Invariants Check:            True
```

### 5.4 Frontend Production Build
```powershell
npm run build --prefix frontend
```
**Output:**
```
vite v8.3.4 building client environment for production...
✓ 1918 modules transformed.
dist/index.html                   0.45 kB │ gzip:  0.29 kB
dist/assets/index-C7PNaBbU.css    9.87 kB │ gzip:  2.63 kB
dist/assets/index-UfCNp3IT.js   349.60 kB │ gzip: 95.45 kB
✓ built in 2.54s
```

---

## 6. System Limitations and Recommended Next Steps

### 6.1 Known Limitations
1. **Host RAM Limitation:** The current machine has 8 GB total RAM with ~0.95 GB free during development. Heavy local models (7B/8B) cannot be loaded without freezing the system.
2. **Synthetic Reference Scores:** Both benchmark suites utilize calibrated synthetic student responses and rubrics. While realistic, they are not historical human teacher marks. Human marking variation across evaluators is typically $\pm 10\text{–}15\%$.
3. **Offline Dependency on Rules for Fine Distinctions:** While the deterministic engine reliably captures formulas, contradictions, and keywords, nuanced argumentative essays require local LLM inference for optimal stylistic evaluation.

### 6.2 Recommended Next Steps
1. **Deploy `qwen2.5:1.5b-instruct` under Ollama:** Once host permissions allow, install Ollama and pull `qwen2.5:1.5b-instruct` to enable genuine local LLM qualitative evaluation.
2. **Collect Real Teacher Marking Batches:** Partner with KTU faculty to collect 50–100 anonymized, human-graded exam papers to calibrate rubrics against real-world handwriting and teacher grading styles.
3. **RAM Upgrade Recommendation:** For institutional production deployment hosting 7B–8B evaluation models, a machine with at least **16 GB RAM** and a discrete GPU (e.g., NVIDIA RTX 3060 12GB or higher) is strongly recommended.
