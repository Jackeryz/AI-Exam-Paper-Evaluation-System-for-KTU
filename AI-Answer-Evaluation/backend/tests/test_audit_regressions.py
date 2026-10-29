"""Regression test suite for verified defect remediations in KTU AI Evaluation Platform.

Uses the isolated test database fixture and in-process TestClient to prevent any server dependency
or development database pollution.
"""

from pathlib import Path
import pytest
from app.services.question_segmentation.question_segmenter import QuestionSegmenter


def test_question_segmenter_does_not_match_registration_codes():
    """Ensure QuestionSegmenter does not falsely treat tokens like '1R025' or '1st' as questions."""
    segmenter = QuestionSegmenter()
    ocr_sample = (
        "Unit:TV\n"
        "Woodland Whispers\n"
        "1R025\n"
        "Chapter:1 Shakuntalam\n"
        "Summary of the play\n"
    )
    segments = segmenter.segment_text(ocr_sample)
    # None of these lines should be falsely segmented as Question 1R or Question 1
    assert len(segments) == 1
    assert "1R025" in segments[0].extracted_text


def test_question_segmenter_properly_segments_delimited_questions():
    """Ensure valid delimiters like 1(a), 1(b), Q1., Question 2 are cleanly parsed."""
    segmenter = QuestionSegmenter()
    text = (
        "1(a) Explain Article 19 freedoms.\n"
        "Speech and expression are protected.\n"
        "1(b) Discuss directive principles.\n"
        "Welfare state principles.\n"
    )
    segments = segmenter.segment_text(text)
    assert len(segments) == 2
    assert segments[0].question_number == "1(a)"
    assert segments[1].question_number == "1(b)"


def test_override_marks_range_validation(auth_client):
    """Ensure teacher overrides reject marks < 0 or > max_marks."""
    # Create test exam
    ex_res = auth_client.post("/api/v1/exams/", json={
        "title": "Audit Range Validation Exam",
        "subject": "Constitution of India",
        "subject_code": "MCN301",
        "max_marks": 10.0,
        "questions": [{
            "question_number": "1(a)",
            "text": "Explain Article 21",
            "max_marks": 10.0
        }]
    })
    assert ex_res.status_code == 201
    exam_id = ex_res.json()["id"]
    try:
        q_id = ex_res.json()["questions"][0]["id"]

        # Approve reference answer
        approve_res = auth_client.post(f"/api/v1/reference-answers/question/{q_id}/approve", json={
            "ideal_answer": "Article 21 guarantees protection of life and personal liberty.",
            "rubric_criteria": [{"criterion": "Life and Liberty", "allocated_marks": 10.0}]
        })
        assert approve_res.status_code == 200

        # Upload an answer sheet and evaluate to create a real evaluation record
        sample_path = Path("experiments/ocr_sandbox/input/handwritten/IMG-20260804-WA0035 - Krishnendu P B.jpg")
        with open(sample_path, "rb") as f:
            up_res = auth_client.post(
                f"/api/v1/answer-sheets/upload/{exam_id}",
                files={"files": (sample_path.name, f, "image/jpeg")},
                data={"student_identifier": "TEST_STUDENT_RANGE"}
            )
        assert up_res.status_code == 201
        upload_data = up_res.json()
        sheet_id = upload_data[0]["id"] if isinstance(upload_data, list) else upload_data["sheets"][0]["id"]

        # Run OCR extraction
        ocr_res = auth_client.post(f"/api/v1/answer-sheets/{sheet_id}/process-ocr")
        assert ocr_res.status_code == 200

        # Run evaluation
        eval_res = auth_client.post(f"/api/v1/evaluations/sheet/{sheet_id}/run")
        assert eval_res.status_code == 200
        eval_list = eval_res.json() if isinstance(eval_res.json(), list) else eval_res.json().get("evaluations", [])
        assert len(eval_list) > 0
        target_eval = eval_list[0]

        # 1. Attempt negative marks (< 0.0) -> must reject with 400
        neg_res = auth_client.post(f"/api/v1/reviews/evaluations/{target_eval['id']}/override", json={
            "teacher_marks": -5.0,
            "teacher_feedback": "Invalid negative mark"
        })
        assert neg_res.status_code == 400
        assert "between 0.0 and" in neg_res.json()["detail"]

        # 2. Attempt marks > max_marks -> must reject with 400
        excess_res = auth_client.post(f"/api/v1/reviews/evaluations/{target_eval['id']}/override", json={
            "teacher_marks": target_eval["max_marks"] + 5.0,
            "teacher_feedback": "Invalid excess mark"
        })
        assert excess_res.status_code == 400
        assert "between 0.0 and" in excess_res.json()["detail"]

        # 3. Valid mark within bounds -> must succeed with 200
        valid_res = auth_client.post(f"/api/v1/reviews/evaluations/{target_eval['id']}/override", json={
            "teacher_marks": round(target_eval["max_marks"] * 0.8, 1),
            "teacher_feedback": "Valid override approved"
        })
        assert valid_res.status_code == 200
    finally:
        auth_client.delete(f"/api/v1/exams/{exam_id}")


def test_rubric_sum_mismatch_rejection(auth_client):
    """Ensure approving a rubric whose criteria sum != question max marks is rejected with 400."""
    ex_res = auth_client.post("/api/v1/exams/", json={
        "title": "Audit Rubric Sum Mismatch Exam",
        "subject": "Constitution of India",
        "subject_code": "MCN301",
        "max_marks": 10.0,
        "questions": [{
            "question_number": "1(a)",
            "text": "Explain Article 14",
            "max_marks": 10.0
        }]
    })
    assert ex_res.status_code == 201
    exam_id = ex_res.json()["id"]
    try:
        q_id = ex_res.json()["questions"][0]["id"]

        # Criteria sum = 6.0, but question max_marks = 10.0 -> Must reject!
        bad_approve_res = auth_client.post(f"/api/v1/reference-answers/question/{q_id}/approve", json={
            "ideal_answer": "Equality before law.",
            "rubric_criteria": [
                {"criterion": "Equality", "allocated_marks": 3.0},
                {"criterion": "Protection", "allocated_marks": 3.0}
            ]
        })
        assert bad_approve_res.status_code == 400
        assert "must equal question maximum marks" in bad_approve_res.json()["detail"]
    finally:
        auth_client.delete(f"/api/v1/exams/{exam_id}")


def test_ocr_correction_payload_support(auth_client):
    """Ensure /ocr-correction accepts both corrected_text and refined_text."""
    ex_res = auth_client.post("/api/v1/exams/", json={
        "title": "Audit OCR Correction Exam",
        "subject": "Constitution of India",
        "subject_code": "MCN301",
        "max_marks": 10.0,
        "questions": [{
            "question_number": "1(a)",
            "text": "Define basic structure",
            "max_marks": 10.0
        }]
    })
    assert ex_res.status_code == 201
    exam_id = ex_res.json()["id"]
    try:
        sample_path = Path("dataset/student_answers/test_sample.jpg")
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        sample_path.write_bytes(b"Mock JPG answer sheet content")
        with open(sample_path, "rb") as f:
            up_res = auth_client.post(
                f"/api/v1/answer-sheets/upload/{exam_id}",
                files={"files": ("test_sample.jpg", f, "image/jpeg")},
                data={"student_identifier": "TEST_STUDENT_01"}
            )
        assert up_res.status_code == 201
        upload_data = up_res.json()
        sheet_id = upload_data[0]["id"] if isinstance(upload_data, list) else upload_data["answer_sheets"][0]["id"]

        # 1. Test with refined_text (used by frontend api.js)
        put_ref = auth_client.put(f"/api/v1/answer-sheets/{sheet_id}/ocr-correction", json={
            "refined_text": "Refined OCR content for verification."
        })
        assert put_ref.status_code == 200

        # 2. Test with corrected_text
        put_corr = auth_client.put(f"/api/v1/answer-sheets/{sheet_id}/ocr-correction", json={
            "corrected_text": "Corrected OCR content for verification."
        })
        assert put_corr.status_code == 200
    finally:
        auth_client.delete(f"/api/v1/exams/{exam_id}")


def test_pdf_report_export_format(auth_client):
    """Verify PDF export endpoint generates a valid %PDF stream."""
    ex_res = auth_client.post("/api/v1/exams/", json={
        "title": "Audit PDF Export Exam",
        "subject": "Constitution of India",
        "subject_code": "MCN301",
        "max_marks": 10.0,
        "questions": [{
            "question_number": "1(a)",
            "text": "Sample question",
            "max_marks": 10.0
        }]
    })
    assert ex_res.status_code == 201
    exam_id = ex_res.json()["id"]
    try:
        pdf_res = auth_client.get(f"/api/v1/reports/exam/{exam_id}/export?format=pdf")
        assert pdf_res.status_code == 200
        assert "application/pdf" in pdf_res.headers.get("content-type", "")
        assert pdf_res.content.startswith(b"%PDF")
    finally:
        auth_client.delete(f"/api/v1/exams/{exam_id}")
