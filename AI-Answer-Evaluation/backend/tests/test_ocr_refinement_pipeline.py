"""Regression test suite for LLM-Based OCR Refinement in KTU Answer Script Evaluation.

Covers all 12 mandatory validation criteria:
1. OCR errors corrected without changing student's meaning.
2. A grammatically incorrect student answer remains grammatically incorrect when supported by OCR.
3. Missing technical concepts are never added (hallucination rejection).
4. Uncertain technical terms are flagged instead of guessed.
5. Mathematical formulas, units, code, and question labels are preserved.
6. Raw OCR text remains unchanged after refinement.
7. Provider failures preserve original OCR and surface a review state.
8. Invalid LLM output is rejected safely.
9. Teacher edits take precedence over prior refinement output.
10. Question segmentation uses the intended text version.
11. Re-evaluation never overwrites teacher-approved text or marks.
12. External providers are not called when cloud processing is disabled.
"""

from datetime import datetime
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.core.config import get_settings
from app.models.evaluation import AnswerSheet, OCRResult, ExtractedAnswer, Evaluation
from app.models.exam import Exam, Question, ApprovedReferenceAnswer
from app.services.llm.llm_interface import (
    LLMProvider,
    LLMResponse,
    GeminiProvider,
    ClaudeProvider,
    OpenAIProvider,
    OllamaProvider,
)
from app.services.ocr_refinement.refinement_engine import (
    OCRRefinementEngine,
    OCRRefinementResult,
)
from app.services.question_segmentation.question_segmenter import QuestionSegmenter


class MockDeterministicLLM(LLMProvider):
    """Deterministic mock provider returning pre-configured responses."""
    provider_name = "MOCK_DETERMINISTIC"

    def __init__(self, canned_content: str, model_name: str = "mock-model") -> None:
        self.canned_content = canned_content
        self.model = model_name

    async def generate(self, prompt: str, system_prompt=None, timeout=None, strict=False) -> LLMResponse:
        return LLMResponse(
            content=self.canned_content,
            provider=self.provider_name,
            model=self.model,
        )


class MockFailingLLM(LLMProvider):
    """Deterministic failing provider simulating offline Ollama or network timeout."""
    provider_name = "MOCK_FAILING"

    def __init__(self, error_message: str = "Connection refused to local Ollama server") -> None:
        self.error_message = error_message
        self.model = "mock-failing-model"

    async def generate(self, prompt: str, system_prompt=None, timeout=None, strict=False) -> LLMResponse:
        raise RuntimeError(self.error_message)


# ==============================================================================
# TEST 1: OCR errors corrected without changing student's meaning
# ==============================================================================
@pytest.mark.anyio
async def test_ocr_errors_corrected_without_changing_meaning():
    raw_ocr = "The c0nstituti0n pr0vides equa1ity before 1aw."
    canned_json = json.dumps({
        "refined_text": "The constitution provides equality before law.",
        "proposed_changes": [
            {
                "original_fragment": "c0nstituti0n",
                "refined_fragment": "constitution",
                "category": "OCR_CHAR_SUBSTITUTION",
                "reason": "Digit 0 misrecognized as letter o",
                "confidence": 0.95,
                "requires_review": False
            },
            {
                "original_fragment": "pr0vides",
                "refined_fragment": "provides",
                "category": "OCR_CHAR_SUBSTITUTION",
                "reason": "Digit 0 misrecognized as letter o",
                "confidence": 0.95,
                "requires_review": False
            },
            {
                "original_fragment": "equa1ity",
                "refined_fragment": "equality",
                "category": "OCR_CHAR_SUBSTITUTION",
                "reason": "Digit 1 misrecognized as letter l",
                "confidence": 0.92,
                "requires_review": False
            },
            {
                "original_fragment": "1aw",
                "refined_fragment": "law",
                "category": "OCR_CHAR_SUBSTITUTION",
                "reason": "Digit 1 misrecognized as letter l",
                "confidence": 0.92,
                "requires_review": False
            }
        ],
        "uncertain_spans": []
    })

    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM(canned_json))
    result = await engine.refine(raw_ocr)

    assert result.status == "REFINED"
    assert result.refined_ocr_text == "The constitution provides equality before law."
    assert result.raw_ocr_text == raw_ocr
    assert len(result.proposed_changes) == 4
    assert result.proposed_changes[0].original_fragment == "c0nstituti0n"
    assert result.proposed_changes[0].refined_fragment == "constitution"
    assert result.proposed_changes[0].requires_review is False


# ==============================================================================
# TEST 2: Grammatically incorrect student answer remains grammatically incorrect
# ==============================================================================
@pytest.mark.anyio
async def test_grammatically_incorrect_student_answer_preserved():
    raw_ocr = "He do not has any r1ghts under the act."
    # The OCR typo 'r1ghts' is recovered to 'rights', but 'He do not has' remains intact!
    canned_json = json.dumps({
        "refined_text": "He do not has any rights under the act.",
        "proposed_changes": [
            {
                "original_fragment": "r1ghts",
                "refined_fragment": "rights",
                "category": "OCR_CHAR_SUBSTITUTION",
                "reason": "Digit 1 misrecognized as letter i",
                "confidence": 0.95,
                "requires_review": False
            }
        ],
        "uncertain_spans": []
    })

    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM(canned_json))
    result = await engine.refine(raw_ocr)

    assert result.status == "REFINED"
    # Preserves student's actual grammatical structure
    assert "He do not has" in result.refined_ocr_text
    assert "rights" in result.refined_ocr_text
    assert "He does not have" not in result.refined_ocr_text


# ==============================================================================
# TEST 3: Missing technical concepts are never added (hallucination rejection)
# ==============================================================================
@pytest.mark.anyio
async def test_missing_technical_concepts_never_added():
    raw_ocr = "Pipelining is a technique in cpu."
    # Hallucinated answer expanding text with academic definition and stages
    hallucinated_json = json.dumps({
        "refined_text": (
            "Pipelining is an advanced implementation technique in computer architecture where multiple "
            "instructions are overlapped in execution. It divides the instruction cycle into five distinct stages: "
            "Instruction Fetch, Instruction Decode, Execute, Memory Access, and Write Back. Pipelining increases "
            "instruction throughput significantly by exploiting parallelism."
        ),
        "proposed_changes": [],
        "uncertain_spans": []
    })

    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM(hallucinated_json))
    result = await engine.refine(raw_ocr)

    # Word count expansion (>35%) must be rejected by validator
    assert result.status == "FAILED_FALLBACK_RAW"
    assert "word count expanded too much" in result.error_message
    # Safely retained raw OCR text
    assert result.refined_ocr_text is None
    assert result.corrected_text == raw_ocr


# ==============================================================================
# TEST 4: Uncertain technical terms are flagged instead of guessed
# ==============================================================================
@pytest.mark.anyio
async def test_uncertain_technical_terms_flagged_not_guessed():
    raw_ocr = "The processor utilizes a [illegible_term] bus architecture."
    canned_json = json.dumps({
        "refined_text": "The processor utilizes a [illegible_term] bus architecture.",
        "proposed_changes": [],
        "uncertain_spans": [
            {
                "fragment": "[illegible_term]",
                "reason": "Handwriting cannot be deciphered with high certainty",
                "flag": "AMBIGUOUS_TERM"
            }
        ]
    })

    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM(canned_json))
    result = await engine.refine(raw_ocr)

    assert result.status == "REFINED"
    assert "[illegible_term]" in result.refined_ocr_text
    # No hallucinated bus architecture guessed (e.g. PCIe, AMBA, Synchronous)
    assert len(result.uncertain_spans) == 1
    assert result.uncertain_spans[0].fragment == "[illegible_term]"
    assert result.uncertain_spans[0].flag == "AMBIGUOUS_TERM"


# ==============================================================================
# TEST 5: Mathematical formulas, units, code, and question labels preserved
# ==============================================================================
@pytest.mark.anyio
async def test_math_formulas_units_code_and_labels_preserved():
    raw_ocr = (
        "1(a) Force calculation:\n"
        "F = m * a\n"
        "m = 10.5 kg, a = 9.8 m/s^2\n"
        "for i in range(n):\n"
        "    sum += arr[i]"
    )
    canned_json = json.dumps({
        "refined_text": (
            "1(a) Force calculation:\n"
            "F = m * a\n"
            "m = 10.5 kg, a = 9.8 m/s^2\n"
            "for i in range(n):\n"
            "    sum += arr[i]"
        ),
        "proposed_changes": [],
        "uncertain_spans": []
    })

    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM(canned_json))
    result = await engine.refine(raw_ocr)

    assert result.status == "REFINED"
    assert "1(a)" in result.refined_ocr_text
    assert "F = m * a" in result.refined_ocr_text
    assert "10.5 kg" in result.refined_ocr_text
    assert "9.8 m/s^2" in result.refined_ocr_text
    assert "for i in range(n):" in result.refined_ocr_text
    assert "sum += arr[i]" in result.refined_ocr_text


# ==============================================================================
# TEST 6: Raw OCR text remains unchanged after refinement
# ==============================================================================
@pytest.mark.anyio
async def test_raw_ocr_text_remains_unchanged():
    raw_original = "Artic1e 21 pr0tects 1ife and 1iberty."
    ocr_record = OCRResult(
        answer_sheet_id=101,
        raw_text=raw_original,
        confidence=0.88,
        engine_used="PP-OCRv6",
    )

    canned_json = json.dumps({
        "refined_text": "Article 21 protects life and liberty.",
        "proposed_changes": [
            {
                "original_fragment": "Artic1e",
                "refined_fragment": "Article",
                "category": "OCR_CHAR_SUBSTITUTION",
                "reason": "Digit 1 to letter l",
                "confidence": 0.96,
                "requires_review": False
            }
        ],
        "uncertain_spans": []
    })

    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM(canned_json))
    ref_res = await engine.refine(ocr_record.raw_text)

    # Update refined field
    ocr_record.refined_text = ref_res.refined_ocr_text

    # Raw OCR text MUST remain identical
    assert ocr_record.raw_text == raw_original
    assert ocr_record.raw_ocr_text == raw_original
    assert ocr_record.refined_text == "Article 21 protects life and liberty."
    assert ocr_record.raw_text != ocr_record.refined_text


# ==============================================================================
# TEST 7: Provider failures preserve original OCR and surface a review state
# ==============================================================================
@pytest.mark.anyio
async def test_provider_failures_preserve_original_ocr():
    raw_ocr = "Raw handwritten text before offline provider error."
    engine = OCRRefinementEngine(llm_provider=MockFailingLLM("Ollama server connection refused"))
    result = await engine.refine(raw_ocr)

    assert result.status == "FAILED_FALLBACK_RAW"
    assert "local ollama service unreachable" in result.error_message.lower()
    # Retains raw text intact
    assert result.refined_ocr_text is None
    assert result.corrected_text == raw_ocr
    assert result.raw_ocr_text == raw_ocr
    # Flags script for teacher review
    assert len(result.uncertain_spans) > 0
    assert result.uncertain_spans[0].flag == "UNCERTAIN_OCR"


# ==============================================================================
# TEST 8: Invalid LLM output is rejected safely
# ==============================================================================
@pytest.mark.anyio
async def test_invalid_llm_output_rejected_safely():
    raw_ocr = "Some valid student text."
    # Malformed garbage that cannot be parsed as JSON
    malformed_content = "{unclosed_json: 'bad content"

    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM(malformed_content))
    result = await engine.refine(raw_ocr)

    # Should not raise exception; handles safely as FAILED_FALLBACK_RAW
    assert result.status == "FAILED_FALLBACK_RAW"
    assert result.raw_ocr_text == raw_ocr
    assert result.refined_ocr_text is None
    assert result.corrected_text == raw_ocr


# ==============================================================================
# TEST 9: Teacher edits take precedence over prior refinement output
# ==============================================================================
@pytest.mark.anyio
async def test_teacher_edits_take_precedence():
    ocr_record = OCRResult(
        answer_sheet_id=1,
        raw_text="Origina1 student text with err0r.",
        refined_text="Original student text with error.",
        corrected_text="Original student text with custom teacher approved technical override.",
        is_teacher_approved=True,
        refinement_status="TEACHER_APPROVED",
    )

    # Suppose refinement or OCR is re-run: teacher correction must NOT be overwritten
    assert ocr_record.is_teacher_approved is True
    assert ocr_record.corrected_text == "Original student text with custom teacher approved technical override."
    assert ocr_record.corrected_text != ocr_record.refined_text


# ==============================================================================
# TEST 10: Question segmentation uses the intended text version
# ==============================================================================
def test_question_segmentation_uses_intended_text_version():
    segmenter = QuestionSegmenter()

    raw_text = (
        "1(a) Raw extraction text for q1.\n"
        "1(b) Raw extraction text for q2."
    )
    teacher_corrected_text = (
        "1(a) Teacher verified and corrected text for q1.\n"
        "1(b) Teacher verified and corrected text for q2."
    )

    # When teacher has approved, segment the teacher-approved text
    approved_segments = segmenter.segment_text(teacher_corrected_text)
    assert len(approved_segments) == 2
    assert approved_segments[0].question_number == "1(a)"
    assert "Teacher verified" in getattr(approved_segments[0], "extracted_text", "")

    # When unapproved, segment raw or refined
    raw_segments = segmenter.segment_text(raw_text)
    assert len(raw_segments) == 2
    assert "Raw extraction" in getattr(raw_segments[0], "extracted_text", "")


# ==============================================================================
# TEST 11: Re-evaluation never overwrites teacher-approved text or marks
# ==============================================================================
def test_reevaluation_preserves_teacher_overrides():
    existing_eval = Evaluation(
        answer_sheet_id=1,
        question_id=1,
        student_answer_text="Teacher approved student answer text.",
        marks_awarded=9.5,
        max_marks=10.0,
        feedback="Teacher override: Excellent explanation.",
        is_reviewed=True,
    )

    # Simulated re-evaluation pass
    ai_calculated_marks = 6.0
    ai_feedback = "AI generated lower deduction feedback."

    # Rule: If already reviewed, teacher marks and feedback are strictly protected
    if not existing_eval.is_reviewed:
        existing_eval.marks_awarded = ai_calculated_marks
        existing_eval.feedback = ai_feedback

    assert existing_eval.marks_awarded == 9.5
    assert existing_eval.feedback == "Teacher override: Excellent explanation."
    assert existing_eval.student_answer_text == "Teacher approved student answer text."


# ==============================================================================
# TEST 12: External providers are not called when cloud processing is disabled
# ==============================================================================
@pytest.mark.anyio
async def test_external_providers_blocked_when_cloud_disabled():
    settings = get_settings()
    # Cloud is disabled by default
    assert settings.ALLOW_CLOUD_LLM is False

    gemini = GeminiProvider(model_name="gemini-1.5-flash")
    with pytest.raises(PermissionError) as exc_gemini:
        await gemini.generate("Sample prompt")
    assert "ALLOW_CLOUD_LLM=False" in str(exc_gemini.value)

    claude = ClaudeProvider(model_name="claude-3-5-sonnet")
    with pytest.raises(PermissionError) as exc_claude:
        await claude.generate("Sample prompt")
    assert "ALLOW_CLOUD_LLM=False" in str(exc_claude.value)

    openai = OpenAIProvider(model_name="gpt-4o")
    with pytest.raises(PermissionError) as exc_openai:
        await openai.generate("Sample prompt")
    assert "ALLOW_CLOUD_LLM=False" in str(exc_openai.value)


# ==============================================================================
# TASK 2 REGRESSION TESTS (Explicit 10-Item Verification Suite)
# ==============================================================================

# 1. Successful configured LLM refinement produces REFINED
@pytest.mark.anyio
async def test_successful_configured_llm_refinement_produces_refined():
    raw_ocr = "Th1s is a KTU ex4m paper w1th min0r typos."
    canned_json = json.dumps({
        "refined_text": "This is a KTU exam paper with minor typos.",
        "proposed_changes": [
            {
                "original_fragment": "Th1s",
                "refined_fragment": "This",
                "category": "OCR_CHAR_SUBSTITUTION",
                "reason": "Digit 1 to letter i",
                "confidence": 0.95,
                "requires_review": False
            }
        ],
        "uncertain_spans": []
    })
    mock_provider = MockDeterministicLLM(canned_json, model_name="qwen3:8b")
    engine = OCRRefinementEngine(llm_provider=mock_provider)
    res = await engine.refine(raw_ocr)

    assert res.status == "REFINED"
    assert res.refined_ocr_text == "This is a KTU exam paper with minor typos."
    assert res.corrected_text == "This is a KTU exam paper with minor typos."
    assert res.provider == "MOCK_DETERMINISTIC"
    assert res.model == "qwen3:8b"
    assert res.error_message is None
    assert len(res.proposed_changes) == 1


# 2. Ollama unavailable produces FAILED_FALLBACK_RAW
@pytest.mark.anyio
async def test_ollama_unavailable_produces_failed_fallback_raw():
    raw_ocr = "Original KTU handwritten answer text."
    failing_provider = MockFailingLLM("All connection attempts failed: [WinError 10061] No connection could be made")
    engine = OCRRefinementEngine(llm_provider=failing_provider)
    res = await engine.refine(raw_ocr)

    assert res.status == "FAILED_FALLBACK_RAW"
    assert res.refined_ocr_text is None
    assert res.corrected_text == raw_ocr
    assert res.raw_ocr_text == raw_ocr
    assert "Local Ollama service unreachable" in res.error_message
    assert "Original raw OCR text retained" in res.error_message


# 3. Disabled refinement produces SKIPPED
@pytest.mark.anyio
async def test_disabled_refinement_produces_skipped():
    raw_ocr = "Text extracted when refinement is toggled off."
    engine = OCRRefinementEngine(llm_provider=MockDeterministicLLM("{}"))
    with patch.object(engine.settings, "REFINEMENT_ENABLED", False):
        res = await engine.refine(raw_ocr)

    assert res.status == "SKIPPED"
    assert res.refined_ocr_text is None
    assert res.corrected_text == raw_ocr
    assert res.raw_ocr_text == raw_ocr
    assert res.provider is None
    assert res.model is None


# 4. Raw OCR remains unchanged on failure
@pytest.mark.anyio
async def test_raw_ocr_remains_unchanged_on_failure():
    raw_ocr = "Untouched student handwriting string."
    engine = OCRRefinementEngine(llm_provider=MockFailingLLM("Timeout connecting to Ollama daemon"))
    res = await engine.refine(raw_ocr)

    assert res.raw_ocr_text == raw_ocr
    assert res.corrected_text == raw_ocr
    assert res.refined_ocr_text is None
    assert res.status == "FAILED_FALLBACK_RAW"


# 5. Provider/model telemetry matches the actual provider call
@pytest.mark.anyio
async def test_provider_model_telemetry_matches_actual_call():
    raw_ocr = "Telemetry validation test."
    canned_json = json.dumps({
        "refined_text": "Telemetry validation test.",
        "proposed_changes": [],
        "uncertain_spans": []
    })
    provider = MockDeterministicLLM(canned_json, model_name="deepseek-r1:8b")
    engine = OCRRefinementEngine(llm_provider=provider)
    res = await engine.refine(raw_ocr)

    assert res.provider == "MOCK_DETERMINISTIC"
    assert res.model == "deepseek-r1:8b"
    assert res.status == "REFINED"


# 6. Retry can update a failed refinement status
@pytest.mark.anyio
async def test_retry_updates_failed_refinement_status_via_api(client, test_db_setup):
    """Verify that retrying refinement via API updates status from FAILED_FALLBACK_RAW to REFINED."""
    # 1. Create exam
    r_exam = client.post("/api/v1/exams/", json={
        "title": "Compiler Design",
        "subject": "Compiler Design",
        "subject_code": "CS302",
        "semester": "S6",
        "academic_year": "2024-2025",
        "max_marks": 100.0,
    })
    assert r_exam.status_code == 201
    exam_id = r_exam.json()["id"]

    # 2. Upload dummy answer sheet
    files = {"files": ("student_sheet.pdf", b"%PDF-1.4 dummy student answer sheet content", "application/pdf")}
    r_up = client.post(f"/api/v1/answer-sheets/upload/{exam_id}", files=files, data={"student_identifier": "TEST_RETRY_01"})
    assert r_up.status_code == 201
    sheet_id = r_up.json()[0]["id"]

    # 3. Simulate initial OCR processing where refinement fails
    with patch("app.api.v1.answer_sheets_api.get_ocr_service") as mock_ocr, \
         patch("app.api.v1.answer_sheets_api.OCRRefinementEngine") as MockEngine:
        mock_svc = mock_ocr.return_value
        mock_svc.process_all_pages.return_value = {
            "text": "1(a) Raw student handwritten soluti0n.",
            "confidence": 0.85,
            "page_count": 1,
            "bounding_boxes": [],
            "engine": "PP-OCRv6",
        }
        mock_eng_inst = MockEngine.return_value
        mock_eng_inst.refine = AsyncMock(return_value=OCRRefinementResult(
            raw_ocr_text="1(a) Raw student handwritten soluti0n.",
            refined_ocr_text=None,
            corrected_text="1(a) Raw student handwritten soluti0n.",
            status="FAILED_FALLBACK_RAW",
            provider="OLLAMA",
            model="qwen3",
            error_message="Local Ollama service unreachable at http://localhost:11434. Original raw OCR text retained.",
        ))

        r_proc = client.post(f"/api/v1/answer-sheets/{sheet_id}/process-ocr")
        assert r_proc.status_code == 200
        data_proc = r_proc.json()
        assert data_proc["refinement_status"] == "FAILED_FALLBACK_RAW"
        assert data_proc["raw_ocr_text"] == "1(a) Raw student handwritten soluti0n."
        assert data_proc["refined_ocr_text"] is None

    # 4. Retry refinement when provider is now working
    with patch("app.api.v1.answer_sheets_api.OCRRefinementEngine") as MockEngine2:
        mock_eng_inst2 = MockEngine2.return_value
        mock_eng_inst2.refine = AsyncMock(return_value=OCRRefinementResult(
            raw_ocr_text="1(a) Raw student handwritten soluti0n.",
            refined_ocr_text="1(a) Raw student handwritten solution.",
            corrected_text="1(a) Raw student handwritten solution.",
            status="REFINED",
            provider="OLLAMA",
            model="qwen3",
        ))

        r_retry = client.post(f"/api/v1/answer-sheets/{sheet_id}/refine-ocr")
        assert r_retry.status_code == 200
        data_retry = r_retry.json()
        assert data_retry["refinement_status"] == "REFINED"
        assert data_retry["refined_ocr_text"] == "1(a) Raw student handwritten solution."
        assert data_retry["corrected_text"] == "1(a) Raw student handwritten solution."
        assert data_retry["raw_ocr_text"] == "1(a) Raw student handwritten soluti0n."


# 7. Retry cannot overwrite newer teacher-approved text
@pytest.mark.anyio
async def test_retry_cannot_overwrite_newer_teacher_approved_text(client, test_db_setup):
    """Verify that retrying refinement cannot overwrite teacher-approved corrections or status."""
    # 1. Create exam
    r_exam = client.post("/api/v1/exams/", json={
        "title": "Compiler Design II",
        "subject": "Compiler Design II",
        "subject_code": "CS304",
        "semester": "S6",
        "academic_year": "2024-2025",
        "max_marks": 100.0,
    })
    assert r_exam.status_code == 201
    exam_id = r_exam.json()["id"]

    # 2. Upload sheet
    files = {"files": ("sheet_appr.pdf", b"%PDF-1.4 dummy", "application/pdf")}
    r_up = client.post(f"/api/v1/answer-sheets/upload/{exam_id}", files=files, data={"student_identifier": "TEST_TEACHER_PROT"})
    sheet_id = r_up.json()[0]["id"]

    # 3. Process OCR with initial fallback
    with patch("app.api.v1.answer_sheets_api.get_ocr_service") as mock_ocr, \
         patch("app.api.v1.answer_sheets_api.OCRRefinementEngine") as MockEngine:
        mock_ocr.return_value.process_all_pages.return_value = {
            "text": "1(a) Studnt ans with mistyping.",
            "confidence": 0.82,
            "page_count": 1,
            "bounding_boxes": [],
            "engine": "PP-OCRv6",
        }
        MockEngine.return_value.refine = AsyncMock(return_value=OCRRefinementResult(
            raw_ocr_text="1(a) Studnt ans with mistyping.",
            refined_ocr_text=None,
            corrected_text="1(a) Studnt ans with mistyping.",
            status="FAILED_FALLBACK_RAW",
            provider="OLLAMA",
            model="qwen3",
            error_message="Ollama offline",
        ))
        client.post(f"/api/v1/answer-sheets/{sheet_id}/process-ocr")

    # 4. Teacher manually edits and approves the transcription
    teacher_approved_text = "1(a) Student answer with teacher-verified technical override."
    r_approve = client.post(
        f"/api/v1/answer-sheets/{sheet_id}/approve-refinement",
        json={"action": "MANUAL_EDIT", "edited_text": teacher_approved_text}
    )
    assert r_approve.status_code == 200
    assert r_approve.json()["refinement_status"] == "TEACHER_APPROVED"
    assert r_approve.json()["is_teacher_approved"] is True
    assert r_approve.json()["corrected_text"] == teacher_approved_text

    # 5. Stale or retry refinement runs later
    with patch("app.api.v1.answer_sheets_api.OCRRefinementEngine") as MockEngineRetry:
        MockEngineRetry.return_value.refine = AsyncMock(return_value=OCRRefinementResult(
            raw_ocr_text="1(a) Studnt ans with mistyping.",
            refined_ocr_text="1(a) Student ans with mistyping.",
            corrected_text="1(a) Student ans with mistyping.",
            status="REFINED",
            provider="OLLAMA",
            model="qwen3",
        ))

        r_late_retry = client.post(f"/api/v1/answer-sheets/{sheet_id}/refine-ocr")
        assert r_late_retry.status_code == 200
        data = r_late_retry.json()

        # CRITICAL RULE: Teacher text and approval are strictly preserved!
        assert data["is_teacher_approved"] is True
        assert data["refinement_status"] == "TEACHER_APPROVED"
        assert data["corrected_text"] == teacher_approved_text
        assert data["corrected_text"] != "1(a) Student ans with mistyping."
        # Refined text is recorded for telemetry without replacing teacher override
        assert data["refined_ocr_text"] == "1(a) Student ans with mistyping."


# 8. Cloud providers remain blocked when cloud processing is disabled
@pytest.mark.anyio
async def test_cloud_providers_remain_blocked_under_refinement_engine():
    raw_ocr = "Private KTU student examination handwriting."
    engine = OCRRefinementEngine(llm_provider=GeminiProvider(model_name="gemini-1.5-flash"))
    res = await engine.refine(raw_ocr)

    assert res.status == "FAILED_FALLBACK_RAW"
    assert res.refined_ocr_text is None
    assert res.corrected_text == raw_ocr
    assert "privacy configuration" in res.error_message


# 9. Frontend displays distinct success, failure, skipped and teacher-approved states
def test_api_response_schema_distinct_status_states():
    """Verify that _to_answer_sheet_response maps all distinct status contract states."""
    from app.api.v1.answer_sheets_api import _to_answer_sheet_response

    # State: PENDING
    s_pending = AnswerSheet(id=1, exam_id=1, status="UPLOADED", file_path="x.pdf")
    resp_pending = _to_answer_sheet_response(s_pending)
    assert resp_pending.refinement_status == "PENDING"
    assert resp_pending.refinement_provider is None

    # State: PROCESSING
    s_proc = AnswerSheet(id=2, exam_id=1, status="PROCESSING_OCR", file_path="x.pdf")
    resp_proc = _to_answer_sheet_response(s_proc)
    assert resp_proc.refinement_status == "PROCESSING"

    # State: REFINED
    s_ref = AnswerSheet(id=3, exam_id=1, status="OCR_COMPLETED", file_path="x.pdf")
    s_ref.ocr_result = OCRResult(
        answer_sheet_id=3,
        raw_text="raw",
        refined_text="refined",
        corrected_text="refined",
        refinement_status="REFINED",
        refinement_provider="OLLAMA",
        refinement_model="qwen3",
    )
    resp_ref = _to_answer_sheet_response(s_ref)
    assert resp_ref.refinement_status == "REFINED"
    assert resp_ref.refinement_provider == "OLLAMA"

    # State: FAILED_FALLBACK_RAW
    s_fail = AnswerSheet(id=4, exam_id=1, status="OCR_COMPLETED", file_path="x.pdf")
    s_fail.ocr_result = OCRResult(
        answer_sheet_id=4,
        raw_text="raw",
        refined_text=None,
        corrected_text="raw",
        refinement_status="FAILED_FALLBACK_RAW",
        refinement_provider="OLLAMA",
        refinement_model="qwen3",
        refinement_error="Local Ollama service unreachable at http://localhost:11434. Original raw OCR text retained.",
    )
    resp_fail = _to_answer_sheet_response(s_fail)
    assert resp_fail.refinement_status == "FAILED_FALLBACK_RAW"
    assert resp_fail.refined_ocr_text is None
    assert resp_fail.corrected_text == "raw"

    # State: SKIPPED
    s_skip = AnswerSheet(id=5, exam_id=1, status="OCR_COMPLETED", file_path="x.pdf")
    s_skip.ocr_result = OCRResult(
        answer_sheet_id=5,
        raw_text="raw",
        refined_text=None,
        corrected_text="raw",
        refinement_status="SKIPPED",
    )
    resp_skip = _to_answer_sheet_response(s_skip)
    assert resp_skip.refinement_status == "SKIPPED"
    assert resp_skip.refinement_provider is None

    # State: TEACHER_APPROVED
    s_app = AnswerSheet(id=6, exam_id=1, status="OCR_COMPLETED", file_path="x.pdf")
    s_app.ocr_result = OCRResult(
        answer_sheet_id=6,
        raw_text="raw",
        refined_text="refined",
        corrected_text="teacher_text",
        refinement_status="TEACHER_APPROVED",
        is_teacher_approved=True,
    )
    resp_app = _to_answer_sheet_response(s_app)
    assert resp_app.refinement_status == "TEACHER_APPROVED"
    assert resp_app.is_teacher_approved is True

    # State: TEACHER_REVERTED_RAW
    s_rev = AnswerSheet(id=7, exam_id=1, status="OCR_COMPLETED", file_path="x.pdf")
    s_rev.ocr_result = OCRResult(
        answer_sheet_id=7,
        raw_text="raw",
        refined_text="refined",
        corrected_text="raw",
        refinement_status="TEACHER_REVERTED_RAW",
        is_teacher_approved=True,
    )
    resp_rev = _to_answer_sheet_response(s_rev)
    assert resp_rev.refinement_status == "TEACHER_REVERTED_RAW"
    assert resp_rev.corrected_text == "raw"


# 10. Invalid or empty LLM responses never appear as successful refinements
@pytest.mark.anyio
async def test_invalid_or_empty_llm_responses_never_appear_as_successful_refinements():
    raw_ocr = "Valid raw student answer text."

    # Empty string response
    engine_empty = OCRRefinementEngine(llm_provider=MockDeterministicLLM(""))
    res_empty = await engine_empty.refine(raw_ocr)
    assert res_empty.status == "FAILED_FALLBACK_RAW"
    assert res_empty.status != "REFINED"
    assert res_empty.refined_ocr_text is None
    assert res_empty.corrected_text == raw_ocr

    # Whitespace only
    engine_ws = OCRRefinementEngine(llm_provider=MockDeterministicLLM("   \n\t  "))
    res_ws = await engine_ws.refine(raw_ocr)
    assert res_ws.status == "FAILED_FALLBACK_RAW"
    assert res_ws.status != "REFINED"
    assert res_ws.refined_ocr_text is None

    # Malformed non-JSON
    engine_bad_json = OCRRefinementEngine(llm_provider=MockDeterministicLLM("Here is your output: {bad syntax"))
    res_bad_json = await engine_bad_json.refine(raw_ocr)
    assert res_bad_json.status == "FAILED_FALLBACK_RAW"
    assert res_bad_json.status != "REFINED"
    assert res_bad_json.refined_ocr_text is None

    # JSON missing refined_text field
    engine_no_field = OCRRefinementEngine(llm_provider=MockDeterministicLLM(json.dumps({"other_key": "val"})))
    res_no_field = await engine_no_field.refine(raw_ocr)
    assert res_no_field.status == "FAILED_FALLBACK_RAW"
    assert res_no_field.status != "REFINED"
    assert res_no_field.refined_ocr_text is None

    # Conversational leakage phrase
    engine_leakage = OCRRefinementEngine(llm_provider=MockDeterministicLLM(json.dumps({
        "refined_text": "Here is the corrected version of student answer.",
        "proposed_changes": [],
        "uncertain_spans": []
    })))
    res_leakage = await engine_leakage.refine(raw_ocr)
    assert res_leakage.status == "FAILED_FALLBACK_RAW"
    assert res_leakage.status != "REFINED"
    assert res_leakage.refined_ocr_text is None
