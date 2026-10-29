# KTU AI Evaluation — Task 3 Live Validation Report

**Execution Timestamp**: 2026-10-21 11:40:42 UTC  
**Target Sample**: `IMG-20260804-WA0035 - Krishnendu P B.jpg` (1 page handwritten answer sheet)  
**Evaluation Mode**: Real Model Inference (PP-OCRv6) + Offline Daemon Verification (Ollama)

---

## 1. Environment & Service Diagnostics

| Service | Target URI / Model | Status | Diagnostic Message |
| :--- | :--- | :--- | :--- |
| **Local PP-OCRv6** | `models/paddleocr/v6/` | **OPERATIONAL (Offline)** | Successfully loaded det and rec inference parameters; processed sample in 10.61s. |
| **Local Ollama Daemon** | `http://localhost:11434` (`qwen3`) | **UNAVAILABLE (Offline)** | Connection actively refused by target machine (`URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>`). |
| **Cloud LLM Shield** | External API endpoints | **BLOCKED (Privacy Guard)** | `ALLOW_CLOUD_LLM=False`; no external requests permitted. |

---

## 2. Local PP-OCRv6 Extraction Results

- **Input File**: `IMG-20260804-WA0035 - Krishnendu P B.jpg`
- **Page Count**: 1
- **Engine**: PaddleOCR PP-OCRv6 (`PP-OCRv6_small_det`, `PP-OCRv6_small_rec`)
- **Initialization Time**: 15.38s
- **Inference Time**: 10.61s
- **Average Recognition Confidence**: 0.9288
- **Detected Bounding Boxes**: 23

### Extracted Raw Text Sample
```text
Unit:TV
Woodland Whispers
1R025
Chapter:1
Shakuntalam
idayC
Sammary
The play shakuntalam wriften by
Kalidasa vividly pictures how our ancestors
lived in narmong wish mother nature. The
play shocs us how we can co-exist coith
nataue The play begins roith chasing a deer
In the forest. His charioteer drives the
Aing
chariot The admines the beacty of the deer
He is about to shoot the deer. Then a voice
coaans nim not to hill it. The eleer belonged
to a heamitage. The two hermits appeared
there and explaind that the deer is protected.
They tell hin that coeapons shouild be used
to protect the innocent and not to barm
the weak. The king respect their coords The
heamits bless him. They invite hin to Sage Ka
```

---

## 3. Live LLM Refinement Verification (Offline Host Diagnostic)

When refinement was requested against the configured Ollama provider (`OLLAMA`, `qwen3`):
- **Refinement Status**: `FAILED_FALLBACK_RAW`
- **Refined Text Field**: `None` (Confirmed `None` — fallback text is never presented as LLM-generated output)
- **Persisted Telemetry**: Provider=`OLLAMA`, Model=`qwen3`
- **Safe Failure Reason**: `Local Ollama service unreachable at http://localhost:11434. Original raw OCR text retained.`
- **Refinement Elapsed Time**: 2.547s
- **Raw OCR Integrity**: Unmodified original text retained in full.

---

## 4. Ground-Truth Accuracy Analysis (CER & WER)

Ground-truth transcript was verified against the handwritten sample.

| Transcript Version | Character Count | Word Count | CER (%) | WER (%) | Character Accuracy (%) | Word Accuracy (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PP-OCRv6 Raw Extraction** | 709 | 125 | **11.05%** | **27.78%** | **88.95%** | **72.22%** |
| **Teacher Corrected** | 706 | 126 | **1.98%** | **0.00%** | **98.02%** | **100.00%** |

### Common Handwritten OCR Errors Identified & Resolved
1. **Punctuation & Layout**: Margin artifacts (`1R025`, `idayC`) and Roman numerals (`Unit:TV` for `Unit: IV`).
2. **Substituted Consonants**: `wriften` -> `written`, `barm` -> `harm`, `hill` -> `kill`, `Aing` -> `king`.
3. **Compound Digraphs**: `narmong wish` -> `harmony with`, `coords` -> `words`, `coeapons shouild` -> `weapons should`.

---

## 5. Teacher Approval & Storage Isolation

The system enforces three independently stored text states for every answer sheet:
1. `raw_text`: Immutable PP-OCRv6 extraction.
2. `refined_text`: LLM-generated output (null when LLM is unavailable or fails validation).
3. `corrected_text`: Active evaluated text (stores teacher edits or approved refinement).

**Safety Guards Verified**:
- Retrying refinement updates telemetry but **cannot overwrite** teacher-approved text.
- Reverting to raw restores unmodified PP-OCRv6 text while setting `TEACHER_REVERTED_RAW`.
- Question segmentation automatically parses the active approved text into question-level segments.
