"""End-to-End integration test script exercising the full KTU Evaluation pipeline.

Uses the isolated test database fixture and in-process TestClient to ensure complete database
isolation and zero coupling to any external running development server.
"""

from pathlib import Path
import pytest


def test_full_pipeline(auth_client):
    print("\n--- 1. Testing System Health & Telemetry ---")
    health_res = auth_client.get("/health")
    assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
    print("Health check response:", health_res.json())

    print("\n--- 2. Creating Examination with Questions ---")
    exam_payload = {
        "title": "Constitution of India & Professional Ethics",
        "subject": "Constitution of India",
        "subject_code": "MCN301",
        "course_code": "MCN301",
        "total_marks": 20.0,
        "max_marks": 20.0,
        "exam_type": "Regular",
        "academic_year": "2024-2025",
        "semester": "S5",
        "duration_minutes": 120,
        "description": "KTU End Semester Theory Examination for Constitution of India."
    }
    exam_res = auth_client.post("/api/v1/exams/", json=exam_payload)
    assert exam_res.status_code == 201, f"Create exam failed: {exam_res.text}"
    exam_data = exam_res.json()
    exam_id = exam_data["id"]
    exam_code = exam_data["exam_code"]
    print(f"Created Exam ID: {exam_id}, Unique Code: {exam_code}")
    assert exam_code.startswith("KTU-"), "Exam code does not have KTU prefix"

    print("\n--- 3. Configuring Questions & Marks ---")
    questions_payload = [
        {
            "question_number": "1(a)",
            "text": "Explain the fundamental rights guaranteed under Article 19 with reasonable restrictions.",
            "max_marks": 10.0,
            "mandatory_keywords": ["article 19", "freedom of speech", "reasonable restrictions", "sovereignty", "public order"]
        },
        {
            "question_number": "1(b)",
            "text": "Discuss the significance of the Directive Principles of State Policy (DPSP) in Indian governance.",
            "max_marks": 10.0,
            "mandatory_keywords": ["directive principles", "dpsp", "part iv", "welfare state"]
        }
    ]
    q_res = auth_client.post(f"/api/v1/exams/{exam_id}/questions", json=questions_payload)
    assert q_res.status_code == 200, f"Configure questions failed: {q_res.text}"
    exam_with_questions = q_res.json()
    questions_data = exam_with_questions["questions"]
    print(f"Configured {len(questions_data)} questions successfully.")
    q1_id = questions_data[0]["id"]
    q2_id = questions_data[1]["id"]

    print("\n--- 4. Uploading Handwritten Answer Sheet ---")
    sample_file_path = Path("experiments/ocr_sandbox/input/handwritten/IMG-20260804-WA0035 - Krishnendu P B.jpg")
    assert sample_file_path.exists(), f"Sample file not found at {sample_file_path}"
    
    with open(sample_file_path, "rb") as f:
        files = {"files": (sample_file_path.name, f, "image/jpeg")}
        data = {"student_identifier": "TVE21CS045"}
        upload_res = auth_client.post(f"/api/v1/answer-sheets/upload/{exam_id}", files=files, data=data)
    assert upload_res.status_code == 201, f"Upload answer sheet failed: {upload_res.text}"
    uploaded_info = upload_res.json()
    sheet_id = uploaded_info[0]["id"] if isinstance(uploaded_info, list) else uploaded_info["sheets"][0]["id"]
    roll = uploaded_info[0]["student_identifier"] if isinstance(uploaded_info, list) else uploaded_info["sheets"][0]["student_identifier"]
    print(f"Uploaded Answer Sheet ID: {sheet_id}, Roll: {roll}")

    print("\n--- 5. Running Local PP-OCRv6 Extraction ---")
    ocr_res = auth_client.post(f"/api/v1/answer-sheets/{sheet_id}/process-ocr")
    assert ocr_res.status_code == 200, f"OCR processing failed: {ocr_res.text}"
    ocr_data = ocr_res.json()
    print(f"OCR Status: {ocr_data['status']}")
    conf = ocr_data.get('ocr_confidence') or 0.0
    print(f"Confidence: {conf:.2f}")
    raw_ocr = ocr_data.get('raw_ocr_text') or ''
    print(f"Extracted Text Preview: {raw_ocr[:120]}...")
    assert len(raw_ocr) > 0, "No OCR text was extracted"

    print("\n--- 6. Approving Reference Answer & Rubric ---")
    rubric_payload = {
        "ideal_answer": "Article 19 guarantees six basic freedoms including freedom of speech and expression. However, reasonable restrictions can be imposed under Article 19(2) in the interests of sovereignty and integrity of India, public order, decency, or morality.",
        "required_concepts": ["freedom of speech", "reasonable restrictions", "sovereignty", "public order"],
        "mandatory_keywords": ["article 19", "restrictions", "sovereignty"],
        "rubric_criteria": [
            {"criterion": "Statement of Fundamental Rights (Art 19)", "allocated_marks": 3.0, "description": "Accurate identification of Article 19"},
            {"criterion": "Detailed Explanation of Freedoms", "allocated_marks": 4.0, "description": "Explanation of speech, assembly, movement"},
            {"criterion": "Reasonable Restrictions Analysis", "allocated_marks": 3.0, "description": "Discussion of public order and sovereignty limits"}
        ]
    }
    approve_res = auth_client.post(f"/api/v1/reference-answers/question/{q1_id}/approve", json=rubric_payload)
    assert approve_res.status_code == 200, f"Approve reference answer failed: {approve_res.text}"
    print(f"Approved Reference Answer for Q1(a) (Version {approve_res.json()['version']})")

    rubric_payload_q2 = {
        "ideal_answer": "Directive Principles of State Policy (DPSP) are enumerated in Part IV of the Constitution (Articles 36 to 51). They aim to establish a socialist, welfare state promoting social and economic democracy.",
        "required_concepts": ["part iv", "welfare state", "social justice", "directive principles"],
        "mandatory_keywords": ["dpsp", "part iv", "welfare"],
        "rubric_criteria": [
            {"criterion": "DPSP Concept & Constitutional Provisions", "allocated_marks": 5.0, "description": "Articles 36-51, non-justiciable"},
            {"criterion": "Significance in Governance & Welfare State", "allocated_marks": 5.0, "description": "Guiding principles for law making"}
        ]
    }
    approve_res2 = auth_client.post(f"/api/v1/reference-answers/question/{q2_id}/approve", json=rubric_payload_q2)
    assert approve_res2.status_code == 200, f"Approve reference answer failed: {approve_res2.text}"
    print(f"Approved Reference Answer for Q1(b) (Version {approve_res2.json()['version']})")

    print("\n--- 7. Running AI Evaluation on Sheet ---")
    eval_res = auth_client.post(f"/api/v1/evaluations/sheet/{sheet_id}/run")
    assert eval_res.status_code == 200, f"Run evaluation failed: {eval_res.text}"
    eval_data = eval_res.json()
    eval_list = eval_data if isinstance(eval_data, list) else eval_data.get("evaluations", [])
    print(f"Evaluations computed for {len(eval_list)} answers.")
    for ev in eval_list:
        print(f"  Question ID {ev['question_id']}: Marks {ev['marks_awarded']}/{ev['max_marks']}, Conf: {ev['confidence_score']:.2f}, Flagged: {ev['is_flagged']}")
    
    first_eval_id = eval_list[0]["id"]

    print("\n--- 8. Testing Teacher Mark Override & Audit Logging ---")
    override_payload = {
        "teacher_id": 1,
        "teacher_marks": 8.5,
        "teacher_feedback": "Student has captured the essential provisions of Article 19. Hand-drawn diagrams were clear.",
        "comments": "Verified student response against Kerala High Court precedent guidelines."
    }
    override_res = auth_client.post(f"/api/v1/reviews/evaluations/{first_eval_id}/override", json=override_payload)
    assert override_res.status_code == 200, f"Override marks failed: {override_res.text}"
    new_marks = override_res.json().get('marks_awarded') or override_res.json().get('teacher_marks')
    print(f"Teacher override successful. New marks: {new_marks}")

    print("\n--- 9. Retrieving Final Results Summary ---")
    summary_res = auth_client.get(f"/api/v1/reports/exam/{exam_id}/summary")
    assert summary_res.status_code == 200, f"Summary failed: {summary_res.text}"
    summary = summary_res.json()
    student = summary["students"][0]
    print(f"Student: {student['student_identifier']}, Total Awarded: {student['total_awarded']}/{student['max_marks']} ({student['percentage']}%)")
    print(f"Teacher Overridden: {student['has_override']}")

    print("\n--- 10. Testing CSV & Excel Exports ---")
    csv_res = auth_client.get(f"/api/v1/reports/exam/{exam_id}/export?format=csv")
    assert csv_res.status_code == 200 and "text/csv" in csv_res.headers.get("content-type", ""), "CSV export failed"
    print(f"CSV Export Successful ({len(csv_res.content)} bytes). Sample:\n{csv_res.text.strip()[:200]}...")

    excel_res = auth_client.get(f"/api/v1/reports/exam/{exam_id}/export?format=excel")
    assert excel_res.status_code == 200, "Excel export failed"
    print(f"Excel Export Successful ({len(excel_res.content)} bytes).")

    print("\n--- 11. Testing Dashboard Metrics Aggregation ---")
    dash_res = auth_client.get("/api/v1/analytics/dashboard")
    assert dash_res.status_code == 200, "Dashboard fetch failed"
    dash = dash_res.json()
    print("Dashboard metrics:", {
        "total_exams": dash["total_exams"],
        "total_answer_sheets": dash["total_answer_sheets"],
        "total_evaluations": dash["total_evaluations"],
        "pending_reviews": dash["pending_reviews"],
    })
    assert dash["total_exams"] >= 1
    # Clean up test exam so database remains clean
    del_res = auth_client.delete(f"/api/v1/exams/{exam_id}")
    assert del_res.status_code == 204

    print("\n=======================================================")
    print("[SUCCESS] ALL 11 END-TO-END WORKFLOW PHASES PASSED 100%!")
    print("=======================================================\n")
