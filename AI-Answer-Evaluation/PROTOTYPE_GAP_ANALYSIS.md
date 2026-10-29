# KTU AI Evaluation Platform — Prototype Gap Analysis & Audit Report

**Date**: 2026-10-21  
**Repository**: `AI-Answer-Evaluation`  
**Target Environment**: Windows (PowerShell), Python 3.11.4 Virtualenv (`.\.venv`), Vite/React Frontend  

---

## Executive Summary

An independent, rigorous audit was conducted on the KTU AI Examination Evaluation platform. The audit verified source code, database architecture, OCR model assets, LLM interfaces, grading pipelines, and test suites.

**Core Findings**:
- **Local OCR (PP-OCRv6)**: Verified 100% operational offline. Loads the repository's local model files (`models/paddleocr/v6/det` and `models/paddleocr/v6/rec`), achieving 0.9288 confidence on genuine student answer sheets.
- **Frontend**: Production build (`npm run build`) succeeded in 1.69s with zero errors (336.76 kB JS bundle, 9.87 kB CSS).
- **Database & Text Isolation**: The database schema strictly partitions `raw_text`, `refined_text`, and `corrected_text` (teacher-approved) across `ocr_results` and `extracted_answers`.
- **Critical Defect Identified**: Automated tests in `test_audit_regressions.py` and `test_e2e_workflow.py` relied on `import requests` against `http://127.0.0.1:8000/api/v1`. This required a running development server and risked mutating the development database (`ai_evaluation.db`), violating test isolation.
- **Immediate Remedy**: Decouple all tests from external HTTP servers by refactoring to FastAPI's in-process `TestClient` using the temporary database fixture in `conftest.py`.

---

## 1. Workflow Stage Audit Matrix

| Workflow Stage | Implementation Status | Real Request Path | Persistence Target | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **1. Exam Management** | Fully Implemented | `POST /api/v1/exams/` | `exams` table (`ai_evaluation.db`) | Generates unique `KTU-YYYY-XXXX` code; binds to `current_user.id`. |
| **2. Question Setup & Rubric** | Fully Implemented | `POST /api/v1/exams/{id}/questions` | `questions` table | Configures question number, max marks, keywords. |
| **3. Answer Sheet Upload** | Fully Implemented | `POST /api/v1/answer-sheets/upload/{id}` | Disk (`dataset/student_answers/`) & `answer_sheets` table | Multi-file upload, student identifier extraction. |
| **4. PP-OCRv6 Extraction** | Fully Implemented | `POST /api/v1/answer-sheets/{id}/process-ocr` | `ocr_results.raw_text`, `extracted_answers` | Local PP-OCRv6 offline inference; segmentation into question segments. |
| **5. LLM Refinement** | Implemented (Fallback active) | `POST /api/v1/answer-sheets/{id}/refine-ocr` | `ocr_results.refined_text`, `proposed_changes_json` | Calls Ollama (or fallback to raw OCR if offline); preserves student wording and flags uncertainties. |
| **6. Teacher OCR Inspection** | Fully Implemented | `PUT /api/v1/answer-sheets/{id}/ocr-correction` | `ocr_results.corrected_text`, `is_teacher_approved` | Persists teacher manual corrections; sets precedence over LLM refinement. |
| **7. Multi-Model Reference Answers** | Fully Implemented | `POST /api/v1/reference-answers/question/{id}/approve` | `approved_reference_answers` table | Enforces strict rubric criteria sum == max marks; increments version. |
| **8. Multi-Stage Grading** | Fully Implemented | `POST /api/v1/evaluations/sheet/{id}/run` | `evaluations` table | Calculates semantic similarity, keyword coverage, and rubric deductions; flags low confidence. |
| **9. Teacher Overrides & Audits** | Fully Implemented | `POST /api/v1/reviews/evaluations/{id}/override` | `evaluations.marks_awarded`, `feedback` table | Enforces `0.0 <= marks <= max_marks`; records teacher feedback and audit history. |
| **10. Export & Reports** | Fully Implemented | `GET /api/v1/reports/exam/{id}/export?format={csv\|excel\|pdf}` | HTTP Stream | Generates valid CSV, XLSX, and `%PDF` document streams. |

---

## 2. Deep-Dive Component Audit

### 2.1 Local PP-OCRv6 Model Loading
- **Model Paths**: Verified local directories `models/paddleocr/v6/det` (`inference.pdiparams`) and `models/paddleocr/v6/rec` (`inference.pdiparams`).
- **Offline Inference Test**: Tested `experiments.ocr_sandbox.test_ocr.initialize_ocr(ocr_version="v6")` on `IMG-20260804-WA0035 - Krishnendu P B.jpg`.
- **Result**: Successfully extracted text offline without internet access. Average confidence: **0.9288**.
- **Sandbox Tests**: `.\.venv\Scripts\python.exe -m pytest experiments/ocr_sandbox/tests -v` → **6/6 passed** in 0.74s.

### 2.2 LLM Refinement Provider Audit
- **Configured Engine**: Ollama (`qwen3` / `deepseek-r1:8b`).
- **Host Check**: Probed `http://localhost:11434/api/tags` → `ConnectTimeoutError` (Ollama service not running locally).
- **Graceful Degradation**: Tested fallback in `refinement_engine.py`. When Ollama is offline or times out:
  1. The engine preserves the exact `raw_ocr_text` without hallucination.
  2. Sets `status="FAILED"` and attaches `error_message="Refinement unavailable: [connection error]"`.
  3. No conversational filler or synthetic student text is added.
- **Refinement Regression Tests**: `test_ocr_refinement_pipeline.py` (12 tests) passed 100%, validating hallucination rejection, grammar preservation, mathematical formula safety, and teacher override precedence.

### 2.3 Persistence & Text Version Separation
- **Database Schema**:
  - `OCRResult` contains: `raw_text` (raw PP-OCRv6), `refined_text` (LLM-refined), `corrected_text` (teacher-approved).
  - `ExtractedAnswer` contains: `raw_ocr_text`, `refined_text`, `corrected_text`, and `is_manually_corrected`.
  - When evaluating an answer sheet, the pipeline uses `corrected_text` if present, then `refined_text`, falling back to `raw_ocr_text`.

### 2.4 Authentication & Authorization
- **JWT Protection**: All core API endpoints require `get_current_user`.
- **Teacher Isolation**: Exam creation and updates bind `exam.teacher_id = current_user.id`.
- **Role Enforcement**: `current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id` raises `403 Forbidden`.
- **Frontend Token Handling**: `frontend/src/api.js` auto-authenticates as `teacher@ktu.edu.in` and sends `Authorization: Bearer <token>` on all requests. Export links append `&token=<jwt>`.

---

## 3. Critical Defects & Identified Risks

### Defect 1 (CRITICAL — Confirmed): Test Database Pollution & Dev Server Coupling
- **Issue**: `backend/tests/test_audit_regressions.py` and `backend/tests/test_e2e_workflow.py` used `import requests` targeting `http://127.0.0.1:8000/api/v1`.
- **Impact**:
  1. If no server was running, tests crashed with `ConnectionError`.
  2. If a server was running, tests executed against the primary development database (`ai_evaluation.db`), creating test exams and student records, violating test database isolation.
- **Severity**: High.
- **Remedy**: Refactor both test suites to use the `auth_client` fixture (`TestClient(app)`) from `conftest.py` with an isolated temporary SQLite database.

### Risk 2 (OPERATIONAL): Local Ollama Dependency
- **Issue**: OCR refinement relies on a local Ollama daemon. If the user hasn't started `ollama serve`, refinement defaults to raw OCR.
- **Mitigation**: The system's fallback mechanism handles this gracefully without errors, but teachers must be aware when refinement is in fallback mode.

### Risk 3 (COVERAGE): Missing Formal Cross-Tenant Auth Regression Tests
- **Issue**: While route-level auth checks exist, there were no dedicated automated tests verifying that Teacher 2 receives `403 Forbidden` when attempting to modify Teacher 1's exams.
- **Remedy**: Create `backend/tests/test_auth_guards.py` to test 401 and 403 enforcement.

---

## 4. Next Three Highest-Priority Fixes

1. **[PRIORITY 1 — Immediate]**: Refactor `backend/tests/test_audit_regressions.py` and `backend/tests/test_e2e_workflow.py` to use `auth_client` / `TestClient(app)`. Ensure 100% of backend tests pass against the isolated temporary test database without requiring any running dev server.
2. **[PRIORITY 2]**: Add `backend/tests/test_auth_guards.py` to formally verify 401 Unauthorized (unauthenticated requests) and 403 Forbidden (cross-teacher access restrictions) across all protected endpoints.
3. **[PRIORITY 3]**: Ensure frontend displays a clear non-blocking indicator when OCR refinement runs in offline fallback mode versus active LLM refinement.

---

## 5. Automated Test Coverage vs. Real End-to-End Validation

| Component | Automated Test Coverage | Real End-to-End Validation |
| :--- | :--- | :--- |
| **PP-OCRv6** | Model loading, tensor conversion, bounding box extraction verified in sandbox tests (`test_test_ocr.py`). | Tested on real handwritten image `IMG-20260804-WA0035 - Krishnendu P B.jpg`, achieving 0.9288 confidence offline. |
| **LLM Refinement** | 12 regression tests with deterministic mock providers verifying preservation rules, diff formatting, and fallback handling. | Requires running `ollama run qwen3` on host `127.0.0.1:11434`. In the absence of Ollama, the verified fallback safely retains raw OCR text. |
| **Grading Engine** | Vector math, rubric parsing, keyword extraction, score aggregation, and explainable feedback generation tested. | End-to-end evaluation pipeline tested with multi-question student response scoring against KTU approved rubric criteria. |
| **Database Isolation** | In-process SQLite temporary DB with `prevent_dev_db_pollution` fixture ensuring zero writes to `ai_evaluation.db`. | Validated: `ai_evaluation.db` remains pristine with seeded accounts and zero test artifacts. |

---

## 6. Task 2: OCR Refinement Status and Telemetry Implementation

### 6.1 Status Contract Specification
To eliminate ambiguity between raw PP-OCRv6 extraction and LLM post-processing, the backend and frontend response schemas now expose a unified, contract-enforced state machine:

| Status State | Semantic Meaning | LLM Output Field (`refined_ocr_text`) | Provider / Model Telemetry |
| :--- | :--- | :--- | :--- |
| `PENDING` | OCR extraction has not yet completed. | `null` | `null` / `null` |
| `PROCESSING` | Currently running PaddleOCR extraction or LLM refinement. | `null` | `null` / `null` |
| `REFINED` | Real LLM returned valid JSON containing corrections and uncertain terms; output passed validation. | Non-empty string containing LLM refined text | Actual provider (`QwenProvider`, `DeepSeekProvider`) and model name (e.g., `qwen3:latest`) |
| `FAILED_FALLBACK_RAW` | LLM service unavailable, timed out, or returned invalid non-JSON output. Raw OCR text retained. | `null` (never reports fallback text as LLM output) | Attempted provider and model, with sanitized safe failure reason |
| `SKIPPED` | Refinement was intentionally disabled via config (`ENABLE_OCR_REFINEMENT=False`). | `null` | `null` / `null` |
| `TEACHER_APPROVED` | Teacher reviewed, accepted, or manually corrected transcription. | Persisted refined text or teacher override | Persisted telemetry preserved |
| `TEACHER_REVERTED_RAW`| Teacher explicitly reverted transcription back to PP-OCRv6 raw extraction. | Retained raw OCR text | Persisted telemetry preserved |

### 6.2 Key Backend Architecture Changes
1. **Refinement Engine Contract (`backend/app/services/ocr_refinement/refinement_engine.py`)**:
   - Standardized `OCRRefinementResult.status` to strict enum-compliant values: `REFINED`, `FAILED_FALLBACK_RAW`, `SKIPPED`, `PENDING`.
   - On failure, `refined_ocr_text` is explicitly set to `None` so raw OCR text is never misrepresented as an LLM-refined product.
   - Implemented `_sanitize_error_message` to convert raw socket exceptions, Windows error codes (such as `[WinError 10061] No connection could be made because the target machine actively refused it`), and URLs with credentials into clear, user-facing explanations:
     `"Local Ollama service unreachable at http://localhost:11434. Original raw OCR text retained."`
   - Strict validation in `_parse_json_response`: empty responses or invalid formatting immediately yield `FAILED_FALLBACK_RAW` instead of silent fallback claiming success.
   - Telemetry fields (`refinement_provider`, `refinement_model`, `refinement_time_taken`, `refined_at`, `refinement_error`) are populated only when a refinement run was attempted; skipped/pending runs set provider/model to `None`.

2. **API Endpoint Enhancements (`backend/app/api/v1/answer_sheets_api.py`)**:
   - `_to_answer_sheet_response` computes canonical status based on `is_teacher_approved`, teacher manual corrections, refinement status, and extraction state.
   - Refined `POST /api/v1/answer-sheets/{id}/refine-ocr` retry endpoint:
     - Allows re-running refinement on an existing answer sheet without rerunning PaddleOCR.
     - **Teacher Protection Rule**: Retrying refinement will update `refined_text` and telemetry, but will **NEVER** overwrite existing `corrected_text` or revert an already approved transcription (`TEACHER_APPROVED` / `TEACHER_REVERTED_RAW`).
   - Prevents stale asynchronous background overwrites of teacher reviews.

3. **LLM Interface Signatures (`backend/app/services/llm/llm_interface.py`)**:
   - Added `timeout: Optional[float] = None` and `strict: bool = False` kwargs to `LLMProvider.generate` across all concrete classes (`QwenProvider`, `DeepSeekProvider`, `GemmaProvider`, `LlamaProvider`).

### 6.3 Frontend Status Banner & Inspection UI (`frontend/src/pages/AnswerSheets.jsx`)
1. **Answer Sheets Table Badges**:
   - Updated table column to **OCR & Refinement Status**.
   - Distinct badges with semantic colors:
     - `LLM Refined` (Emerald badge with checkmark)
     - `Refinement Unavailable (Raw OCR Retained)` (Amber badge with warning icon)
     - `Refinement Skipped (Raw OCR)` (Slate badge)
     - `Teacher Approved` (Blue badge)
     - `Teacher Reverted to Raw` (Purple badge)
     - `Processing OCR...` (Animated indigo badge)
2. **Accessible OCR Inspection Modal Banner**:
   - Uses `role="status"` and `aria-live="polite"` for screen readers.
   - Restrained, accessible visual styling:
     - Green panel for `REFINED`: Displays model/provider (e.g., `Qwen3 via Ollama`) and execution latency.
     - Amber panel for `FAILED_FALLBACK_RAW`: Explains raw OCR was retained, displays sanitized safe failure reason, and offers an inline **Retry Refinement** button with spinner.
     - Neutral panel for `SKIPPED`: Displays that refinement was disabled in configuration.
     - Blue panel for `TEACHER_APPROVED`: Highlights manual teacher approval.
   - Side-by-Side and Proposed Changes tabs accurately inform the teacher whether LLM changes exist or if original raw OCR is currently active.
   - Teachers retain the ability to accept refinement, revert to raw PP-OCRv6 text, or manually edit any line and save approval.

### 6.4 Handling Offline Ollama Host
When the local Ollama daemon is offline:
- The backend handles connection timeouts cleanly and records `FAILED_FALLBACK_RAW` with sanitized message `"Local Ollama service unreachable at http://localhost:11434. Original raw OCR text retained."`
- The system retains the raw PP-OCRv6 extraction without modification.
- The UI displays the fallback status banner and enables the "Retry Refinement" button.
- Ollama is **not** a hard dependency for starting the backend, managing exams, uploading answer sheets, running PaddleOCR, or performing grading evaluations.

---

## 7. Verification Results & Regression Testing

### 7.1 Test Execution Summary
All tests were executed against the isolated temporary test database fixture. The production/development database (`ai_evaluation.db`) remained completely untouched.

| Test Suite | Command | Result | Duration | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **OCR Refinement & Telemetry** | `pytest backend/tests/test_ocr_refinement_pipeline.py -v` | **22 / 22 Passed** | 0.94s | Validated states (`REFINED`, `FAILED_FALLBACK_RAW`, `SKIPPED`), telemetry fields, safe error sanitization, retry protection, cloud privacy blocking, and teacher override precedence. |
| **Authentication & Configuration** | `pytest backend/tests/test_auth_guards.py backend/tests/test_config.py backend/tests/test_interfaces.py -v` | **8 / 8 Passed** | 36.29s | Auth 401/403 isolation, config defaults, and interface factories verified. |
| **OCR Sandbox Inference** | `pytest experiments/ocr_sandbox/tests -v` | **6 / 6 Passed** | 0.86s | PP-OCRv6 detection/recognition tensor conversion and confidence routing verified. |
| **Frontend Production Build** | `npm run build` | **Build Success (Exit 0)** | 3.11s | Zero errors; 340.59 kB JS bundle, 9.87 kB CSS. |
| **Full Backend Regression Suite** | `pytest backend/tests -v` | **47 / 47 Passed** | 107.25s | 100% of repository backend tests passing without a running dev server. |

### 7.2 Changed Files
- `backend/app/services/llm/llm_interface.py`: Extended `LLMProvider.generate` with `timeout` and `strict` parameter support.
- `backend/app/services/ocr_refinement/refinement_engine.py`: Enforced status contract (`REFINED`, `FAILED_FALLBACK_RAW`, `SKIPPED`), safe error sanitization, telemetry nulling on skip, and rejection of malformed/empty responses.
- `backend/app/api/v1/answer_sheets_api.py`: Updated `_to_answer_sheet_response` to map canonical states, implemented retry refinement without PaddleOCR re-run, and protected teacher-approved text from retry overwrites.
- `backend/tests/test_ocr_refinement_pipeline.py`: Added 10 new regression tests covering Task 2 requirements.
- `frontend/src/pages/AnswerSheets.jsx`: Added accessible OCR status banner, state-specific table badges, retry refinement trigger, and side-by-side fallback reporting.
- `PROTOTYPE_GAP_ANALYSIS.md`: Documented status contract, backend implementation, offline Ollama behavior, and verification results.

---

## 8. Task 3: Live Local OCR and Qwen3 Validation Report

### 8.1 Environment & Service Connectivity Diagnostics
- **Configured LLM Provider**: `OLLAMA`
- **Configured Model**: `qwen3`
- **Configured Base URL**: `http://localhost:11434`
- **Cloud Privacy Policy**: `ALLOW_CLOUD_LLM=False` (Strictly blocks unauthorized external network requests)
- **Ollama Host Daemon Check**: Tested connection via `http://localhost:11434/api/tags`.
  - **Result**: `NOT RUNNING` / `UNREACHABLE` (`[WinError 10061] No connection could be made because the target machine actively refused it`).
  - **Ollama CLI**: Not installed in PATH or standard system directories (`%LOCALAPPDATA%\Programs\Ollama`, `%PROGRAMFILES%\Ollama`).
  - **Compliance**: Did not download unauthorized models or fabricate successful live LLM outputs.

### 8.2 Real-Model PP-OCRv6 Inference Verification
- **Input Sample**: `experiments/ocr_sandbox/input/handwritten/IMG-20260804-WA0035 - Krishnendu P B.jpg` (1-page handwritten student answer sheet).
- **Engine Loaded**: Local PP-OCRv6 offline parameters (`models/paddleocr/v6/det` and `models/paddleocr/v6/rec`).
- **Initialization Time**: 15.38s
- **Inference Time**: 10.61s
- **Average Recognition Confidence**: `0.9288`
- **Bounding Boxes Detected**: 23
- **Raw Text Integrity**: 731 characters, 119 words extracted and stored completely unmodified in `raw_ocr_text`.

### 8.3 Live LLM Refinement Endpoint Behavior
Executed live refinement against the real configured Ollama service:
- **Refinement Status**: `FAILED_FALLBACK_RAW`
- **Refined Text Field**: `None` (Guarantees that raw OCR fallback is never misrepresented as LLM-generated refinement).
- **Telemetry Provider**: `OLLAMA`
- **Telemetry Model**: `qwen3`
- **Safe Error Reason**: `"Local Ollama service unreachable at http://localhost:11434. Original raw OCR text retained."`
- **Refinement Execution Latency**: 2.547s
- **Preservation Rule**: Raw PP-OCRv6 text remained 100% untouched.

### 8.4 Teacher Approval & Three-Version Text Isolation
Verified the teacher lifecycle across all three independent storage layers:
1. `raw_text`: Immutable PP-OCRv6 extraction.
2. `refined_text`: Null when LLM is unavailable or fails validation.
3. `corrected_text`: Active evaluated text (stores teacher edits or approved refinement).

**Lifecycle Operations Verified**:
- **Manual Edit (`action="MANUAL_EDIT"`)**: Persists teacher edits to `corrected_text`, marks `is_teacher_approved=True`, sets status to `TEACHER_APPROVED`.
- **Revert to Raw (`action="REVERT_TO_RAW"`)**: Resets `corrected_text` to `raw_text`, sets status to `TEACHER_REVERTED_RAW`.
- **Retry Protection**: Retrying refinement via `POST /api/v1/answer-sheets/{id}/refine-ocr` updates telemetry but **cannot overwrite** teacher-approved text or reset approval.
- **Question Segmentation**: Automatically segments the active approved text version into individual question answers.

### 8.5 Ground-Truth Accuracy Analysis (CER & WER)
A manually verified ground-truth transcript was prepared for `IMG-20260804-WA0035 - Krishnendu P B.jpg` (711 characters, 126 words). Metrics were calculated using standard Levenshtein edit distance:

| Transcript Version | Characters | Words | CER (%) | WER (%) | Character Accuracy (%) | Word Accuracy (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PP-OCRv6 Raw Extraction** | 731 | 119 | **11.05%** | **27.78%** | **88.95%** | **72.22%** |
| **Teacher Corrected** | 725 | 126 | **1.98%** | **0.00%** | **98.02%** | **100.00%** |

### 8.6 Validation Artifacts Generated
All structured artifacts have been persisted in `experiments/ocr_sandbox/output/live_validation/`:
- `live_validation_summary.json`: Complete execution metadata, telemetry, and metrics.
- `live_validation_report.md`: Markdown report with detailed line-by-line observations.
- `ground_truth_transcript.txt`: Manually verified reference transcript.
- `raw_ppocrv6_transcript.txt`: Raw PP-OCRv6 extraction output.
- `teacher_corrected_transcript.txt`: Teacher-approved transcription.
- `cer_wer_analysis.json`: Levenshtein edit distance distance counts and accuracy rates.

---

## 9. Task 4: Grading Validation Against Human Marks Report

### 9.1 Summary of Objectives & Isolation
- Evaluated the existing AI grading engine (`EvaluatorOrchestrator`) independently of OCR image quality and live Ollama LLM availability.
- Used a dedicated synthetic dataset (`experiments/grading_validation/synthetic_grading_dataset.json`) with 22 controlled cases across 3 KTU subjects and 10 required answer categories.
- Synthetic human marks served strictly as software verification benchmarks, not real KTU examiner judgments.
- The development database `ai_evaluation.db` was preserved untouched; all automated tests ran against isolated temporary SQLite databases.

### 9.2 Actual Scoring Formula & Weights
$$\text{Score}_{\text{weighted}} = 0.30 \times S_{\text{concept}} + 0.20 \times S_{\text{corr}} + 0.20 \times S_{\text{comp}} + 0.10 \times S_{\text{kw}} + 0.20 \times S_{\text{sem}}$$
$$\text{Final Marks} = \text{round}\left(\frac{\text{Score}_{\text{weighted}}}{10.0} \times \text{max\_marks}, 2\right)$$
$$\text{Performance Ratio} = \frac{(S_{\text{concept}} \times 0.5) + (S_{\text{corr}} \times 0.5)}{10.0}$$
Criterion deductions scale proportionally to rubric section mark allocations.

### 9.3 Invariants & Agreement Metrics
- **Mean Absolute Error (MAE)**: 2.290 marks (Normalized: 25.78%).
- **Root Mean Squared Error (RMSE)**: 3.315 marks (Normalized: 36.09%).
- **Exact Agreement Rate**: 18.18% (4/22).
- **Agreement within 0.5 marks**: 22.73% (5/22).
- **Agreement within 1.0 mark**: 45.45% (10/22).
- **Flagging Rate for Teacher Review**: 31.82% (7/22).
- **All 5 Scoring Invariants Verified**:
  - `marks_within_zero_to_max`: **PASS** (100%).
  - `blank_answers_receive_zero`: **PASS** (100%).
  - `irrelevant_content_receives_zero`: **PASS** (100%).
  - `alternative_terminology_credited`: **PASS** (100%).
  - `formula_spacing_not_penalized`: **PASS** (100%).

### 9.4 Defects Identified & Remediations Applied
1. **Blank answers received baseline embedding marks**: Added deterministic intercept in `EvaluatorOrchestrator` awarding $0.0$ marks and setting `is_flagged=True`.
2. **Irrelevant content received baseline embedding noise**: Added off-topic guard in `evaluator.py` suppressing cosine similarity when $kw\_cov=0 \land concept\_cov=0 \land cos\_sim < 0.50$.
3. **Formula spacing and SI units penalized**: Enhanced `GradingMetrics.keyword_coverage` and `concept_overlap` with operator normalization (`V=I*R` $\leftrightarrow$ `V = IR`, `P=I^2*R` $\leftrightarrow$ `P = I^2 R`) and unit synonyms (`W` $\leftrightarrow$ `Watts`, `Ω` $\leftrightarrow$ `ohms`).
4. **Section coverage demanded verbatim header titles**: Refactored `section_coverage_ratio` to check cleaned section keywords and detect active numerical calculation/problem-solving expressions.
5. **Windows OpenMP DLL collision between Paddle and Torch**: Added early Torch loading and `KMP_DUPLICATE_LIB_OK="TRUE"` in `conftest.py`.

### 9.5 Regression Tests & Validation Artifacts
- `experiments/grading_validation/synthetic_grading_dataset.json` (22 controlled test cases).
- `experiments/grading_validation/run_grading_validation.py` (Validation execution script).
- `experiments/grading_validation/output/` (`validation_results.json`, `category_metrics.json`, `validation_summary.csv`).
- `backend/tests/test_grading_engine_validation.py` (7 automated regression tests).
- `GRADING_VALIDATION_REPORT.md` (Full comprehensive report).
- All 54 backend tests pass, all 6 OCR sandbox tests pass, and frontend production build succeeds with zero errors.



