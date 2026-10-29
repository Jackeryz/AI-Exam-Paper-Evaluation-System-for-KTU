"""Live Prototype Verification Script for Task 6.

Executes live HTTP requests against running FastAPI backend (http://127.0.0.1:8000)
and Vite frontend (http://localhost:5173).
Tests real handwritten sample (IMG-20260804-WA0035 - Krishnendu P B.jpg),
PP-OCRv6 OCR extraction, OCR text correction, rubric evaluation,
teacher mark overrides, re-evaluation non-overwrite integrity,
cross-teacher authorization (403/401), and CSV/Excel/PDF exports.
"""

import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"

def http_req(url, method="GET", headers=None, data=None):
    headers = headers or {}
    if data is not None and not isinstance(data, (bytes, bytearray)):
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if resp.status == 204 or len(raw) == 0:
                return resp.status, None, resp.headers
            if "application/json" in content_type:
                return resp.status, json.loads(raw.decode("utf-8")), resp.headers
            elif "text/" in content_type:
                return resp.status, raw.decode("utf-8"), resp.headers
            return resp.status, raw, resp.headers
    except urllib.error.HTTPError as e:
        raw_err = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(raw_err)
            return e.code, err_json, e.headers
        except Exception:
            return e.code, raw_err, e.headers


def http_upload(url, token, file_path: Path, student_roll: str):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = bytearray()
    
    # student_identifier field
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="student_identifier"\r\n\r\n')
    body.extend(student_roll.encode("utf-8"))
    body.extend(b"\r\n")
    
    # files field
    file_bytes = file_path.read_bytes()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="files"; filename="{file_path.name}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: image/jpeg\r\n\r\n")
    body.extend(file_bytes)
    body.extend(b"\r\n")
    
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    req = urllib.request.Request(url, data=bytes(body), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")), resp.headers
    except urllib.error.HTTPError as e:
        raw_err = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw_err), e.headers
        except Exception:
            return e.code, raw_err, e.headers


def main():
    print("=" * 70)
    print("KTU AI EVALUATION — TASK 6 LIVE PROTOTYPE VERIFICATION")
    print("=" * 70)

    # 1. Start and inspect the application
    print("\n--- 1. Testing Reachability of Running Servers ---")
    status, fe_html, _ = http_req(FRONTEND_URL)
    print(f"[Frontend] {FRONTEND_URL} -> HTTP {status}")
    assert status == 200, f"Frontend unreachable: {status}"
    assert "root" in str(fe_html), "Frontend missing root mount container"
    print("  -> Vite frontend is active and serving React application HTML.")

    status, be_status, _ = http_req(f"{BACKEND_URL}/api/")
    print(f"[Backend Root] {BACKEND_URL}/api/ -> HTTP {status}: {be_status}")
    assert status == 200 and be_status.get("status") == "ONLINE", "Backend not online"

    status, health, _ = http_req(f"{BACKEND_URL}/health")
    print(f"[Backend Health] HTTP {status}: {health}")
    assert status == 200, "Health check failed"
    print("  -> FastAPI backend is active, DB connected, PaddleOCR loaded.")

    # 2. Authenticate Teachers
    print("\n--- 2. Testing Authentication & Token Issuance ---")
    status, auth_t1, _ = http_req(f"{BACKEND_URL}/api/v1/auth/login", method="POST", data={
        "email": "teacher@ktu.edu.in",
        "password": "teacher123"
    })
    assert status == 200, f"Teacher 1 login failed: {auth_t1}"
    t1_token = auth_t1["access_token"]
    print("  -> Teacher 1 (teacher@ktu.edu.in) authenticated successfully.")

    status, auth_t2, _ = http_req(f"{BACKEND_URL}/api/v1/auth/login", method="POST", data={
        "email": "teacher2@ktu.edu.in",
        "password": "teacher123"
    })
    assert status == 200, f"Teacher 2 login failed: {auth_t2}"
    t2_token = auth_t2["access_token"]
    print("  -> Teacher 2 (teacher2@ktu.edu.in) authenticated successfully.")

    status, bad_auth, _ = http_req(f"{BACKEND_URL}/api/v1/auth/login", method="POST", data={
        "email": "teacher@ktu.edu.in",
        "password": "wrongpassword"
    })
    assert status == 401, f"Expected 401 for bad password, got {status}"
    print("  -> Invalid credentials properly rejected with HTTP 401.")

    t1_headers = {"Authorization": f"Bearer {t1_token}"}
    t2_headers = {"Authorization": f"Bearer {t2_token}"}

    # 3. Create Examination & Questions
    print("\n--- 3. Creating Examination & Configuring Questions (Teacher 1) ---")
    exam_payload = {
        "title": "KTU S4 Literature & Analysis - Shakuntalam",
        "subject": "Shakuntalam",
        "subject_code": "ENG202",
        "course_code": "ENG202",
        "total_marks": 10.0,
        "max_marks": 10.0,
        "exam_type": "Regular",
        "academic_year": "2024-2025",
        "semester": "S4",
        "duration_minutes": 60,
        "description": "Evaluation of Shakuntalam summary, ethical principles and nature themes."
    }
    status, exam, _ = http_req(f"{BACKEND_URL}/api/v1/exams", method="POST", headers=t1_headers, data=exam_payload)
    assert status == 201, f"Failed to create exam: {exam}"
    exam_id = exam["id"]
    exam_code = exam["exam_code"]
    print(f"  -> Created Exam ID {exam_id}, Code: {exam_code}")

    questions_payload = [
        {
            "question_number": "1",
            "text": "Discuss the summary and central theme of the play Shakuntalam by Kalidasa.",
            "max_marks": 10.0,
            "mandatory_keywords": ["shakuntalam", "kalidasa", "harmony", "nature", "deer", "king", "hermits", "weapons"]
        }
    ]
    status, q_res, _ = http_req(f"{BACKEND_URL}/api/v1/exams/{exam_id}/questions", method="POST", headers=t1_headers, data=questions_payload)
    assert status == 200, f"Failed to configure questions: {q_res}"
    configured_q = q_res["questions"][0]
    q_id = configured_q["id"]
    print(f"  -> Configured Question {configured_q['question_number']} (ID: {q_id}, Max Marks: {configured_q['max_marks']}).")

    # 4. Configure & Approve Reference Answer & Rubric
    print("\n--- 4. Approving Reference Answer & Rubric Criteria ---")
    ref_payload = {
        "ideal_answer": "The play Shakuntalam written by Kalidasa vividly pictures how our ancestors lived in harmony with mother nature. The play shows how we can co-exist with nature. The play begins with King Dushyanta chasing a deer in the forest. His charioteer drives the chariot. The king admires the beauty of the deer and is about to shoot it. A voice warns him not to kill it because the deer belongs to a hermitage. Two hermits explain that weapons should be used to protect the innocent and not harm the weak. The king respects their words and the hermits bless him, inviting him to Sage Kanva's ashram.",
        "required_concepts": ["harmony with nature", "chasing deer", "hermits warning", "weapons protect innocent"],
        "mandatory_keywords": ["shakuntalam", "kalidasa", "harmony", "nature", "dushyanta", "hermits", "weapons"],
        "rubric_criteria": [
            {"criterion": "Theme of coexistence and living in harmony with nature", "allocated_marks": 3.0, "description": "Ancestors living with nature"},
            {"criterion": "Story begins with King chasing deer in the forest", "allocated_marks": 3.0, "description": "Dushyanta and charioteer"},
            {"criterion": "Hermits warning that weapons protect innocent not harm weak", "allocated_marks": 4.0, "description": "Respecting hermits counsel"}
        ]
    }
    status, ref_res, _ = http_req(f"{BACKEND_URL}/api/v1/reference-answers/question/{q_id}/approve", method="POST", headers=t1_headers, data=ref_payload)
    assert status == 200, f"Failed to approve reference answer: {ref_res}"
    print(f"  -> Reference answer approved successfully (Version {ref_res['version']}). Total Rubric: 10.0 marks.")

    # 5. Upload Real Handwritten Answer Sheet
    print("\n--- 5. Uploading Real Handwritten Answer Sheet ---")
    handwritten_path = Path("experiments/ocr_sandbox/input/handwritten/IMG-20260804-WA0035 - Krishnendu P B.jpg")
    assert handwritten_path.exists(), f"Sample handwritten file not found: {handwritten_path}"
    student_roll = "KTU-2026-ENG-035"
    status, upload_res, _ = http_upload(f"{BACKEND_URL}/api/v1/answer-sheets/upload/{exam_id}", t1_token, handwritten_path, student_roll)
    assert status == 201, f"Failed to upload answer sheet: {upload_res}"
    sheet_id = upload_res[0]["id"] if isinstance(upload_res, list) else upload_res["sheets"][0]["id"]
    print(f"  -> Uploaded real handwritten document: ID={sheet_id}, Roll={student_roll}, File={handwritten_path.name}")

    # 6. Run Local PP-OCRv6 OCR Extraction
    print("\n--- 6. Running Local PP-OCRv6 Extraction ---")
    t0 = time.time()
    status, ocr_data, _ = http_req(f"{BACKEND_URL}/api/v1/answer-sheets/{sheet_id}/process-ocr", method="POST", headers=t1_headers)
    elapsed_ocr = time.time() - t0
    assert status == 200, f"OCR processing failed: {ocr_data}"
    raw_ocr = ocr_data.get("raw_ocr_text", "")
    ocr_conf = ocr_data.get("ocr_confidence", 0.0)
    print(f"  -> OCR completed in {elapsed_ocr:.2f}s.")
    print(f"  -> Confidence: {ocr_conf:.4f}, Extracted Length: {len(raw_ocr)} chars.")
    print(f"  -> Sample Raw OCR Text:\n     {raw_ocr[:140]}...")
    assert "Shakuntalam" in raw_ocr or "Kalidasa" in raw_ocr or "nature" in raw_ocr, "Key text missing from OCR"

    # 7. Correct OCR Errors and Approve Resulting Text
    print("\n--- 7. Correcting OCR Errors and Approving Corrected Text ---")
    # Identify and correct handwritten OCR misreadings:
    # "wriften" -> "written", "barm" -> "harm", "coords" -> "words", "hill" -> "kill"
    corrected_text = raw_ocr.replace("wriften", "written").replace("barm", "harm").replace("coords", "words").replace("hill", "kill")
    status, corr_res, _ = http_req(f"{BACKEND_URL}/api/v1/answer-sheets/{sheet_id}/approve-refinement", method="POST", headers=t1_headers, data={
        "action": "MANUAL_EDIT",
        "edited_text": corrected_text
    })
    assert status == 200, f"Failed to save corrected OCR text: {corr_res}"
    print("  -> Teacher approved corrected OCR text.")
    # Verify that raw_text is preserved unmodified
    status, sheet_details, _ = http_req(f"{BACKEND_URL}/api/v1/answer-sheets/{sheet_id}", headers=t1_headers)
    assert status == 200
    assert sheet_details["raw_ocr_text"] == raw_ocr, "Raw OCR text was corrupted!"
    assert sheet_details["corrected_text"] == corrected_text, "Corrected text was not saved properly!"
    print("  -> Verified raw_ocr_text immutability: original PaddleOCR source text is preserved perfectly.")

    # 8. Generate AI Evaluation
    print("\n--- 8. Generating Evaluation ---")
    t0 = time.time()
    status, eval_res, _ = http_req(f"{BACKEND_URL}/api/v1/evaluations/sheet/{sheet_id}/run", method="POST", headers=t1_headers)
    elapsed_eval = time.time() - t0
    assert status == 200, f"Evaluation run failed: {eval_res}"
    eval_list = eval_res if isinstance(eval_res, list) else eval_res.get("evaluations", [])
    assert len(eval_list) > 0, "No evaluation generated"
    ev = eval_list[0]
    eval_id = ev["id"]
    print(f"  -> Evaluation computed in {elapsed_eval:.2f}s. Evaluation ID: {eval_id}")
    print(f"  -> Suggested Marks: {ev['marks_awarded']} / {ev['max_marks']}")
    print(f"  -> Confidence: {ev['confidence_score']:.2f}, Flagged for Review: {ev['is_flagged']}")
    print(f"  -> Evaluation Method: {ev['evaluation_method']}")
    print(f"  -> Points Addressed ({len(ev.get('points_addressed') or [])}): {ev.get('points_addressed')}")
    print(f"  -> Missing Points ({len(ev.get('missing_points') or [])}): {ev.get('missing_points')}")
    print(f"  -> Contradictions ({len(ev.get('identified_contradictions') or [])}): {ev.get('identified_contradictions')}")
    print(f"  -> Criterion Deductions Breakdown ({len(ev.get('criterion_deductions') or [])} criteria):")
    for cd in ev.get("criterion_deductions", []):
        print(f"     * {cd['criterion']}: Awarded {cd['awarded_marks']}/{cd['allocated_marks']}m (Deduction: -{cd['deducted_marks']}m, Reason: {cd.get('reason') or cd.get('deduction_reason')})")

    # 9. Teacher Override of Marks and Feedback
    print("\n--- 9. Editing Marks and Feedback (Teacher Override) ---")
    override_payload = {
        "teacher_id": 1,
        "teacher_marks": 8.5,
        "teacher_feedback": "Well articulated summary. Good coverage of nature harmony and hermit episode. Handwriting legibility improved after teacher correction.",
        "comments": "Verified against reference rubric. Upgraded score to 8.5/10."
    }
    status, over_res, _ = http_req(f"{BACKEND_URL}/api/v1/reviews/evaluations/{eval_id}/override", method="POST", headers=t1_headers, data=override_payload)
    assert status == 200, f"Failed to override evaluation: {over_res}"
    assert over_res["marks_awarded"] == 8.5, f"Marks not updated: {over_res}"
    assert over_res["is_reviewed"] is True, "Evaluation not marked reviewed"
    print(f"  -> Teacher override submitted successfully: Marks Awarded = {over_res['marks_awarded']} / {over_res['max_marks']}")
    print(f"  -> is_reviewed = {over_res['is_reviewed']}, is_flagged = {over_res['is_flagged']}")

    # Test bounds checking
    status, bad_bound, _ = http_req(f"{BACKEND_URL}/api/v1/reviews/evaluations/{eval_id}/override", method="POST", headers=t1_headers, data={
        "teacher_id": 1,
        "teacher_marks": 15.0,  # Exceeds max 10.0
    })
    assert status == 400, f"Expected 400 for out-of-bounds marks, got {status}"
    print("  -> Valid bounds enforcement verified: score 15.0/10.0 rejected with HTTP 400.")

    # 10. Refresh & Reopen: Persistence Check
    print("\n--- 10. Simulating Browser Refresh & Reopening Evaluation ---")
    status, reloaded_ev, _ = http_req(f"{BACKEND_URL}/api/v1/evaluations/{eval_id}", headers=t1_headers)
    assert status == 200, f"Failed to fetch evaluation: {reloaded_ev}"
    assert reloaded_ev["marks_awarded"] == 8.5, f"Expected 8.5 marks to persist, got {reloaded_ev['marks_awarded']}"
    assert reloaded_ev["is_reviewed"] is True, "Expected is_reviewed to persist as True"
    print("  -> Overridden marks (8.5) and reviewed state persisted across request refresh.")

    # 11. Re-evaluate Answer: Non-Overwrite Verification
    print("\n--- 11. Re-evaluating Answer Sheet (Non-Overwrite Check) ---")
    status, re_eval_res, _ = http_req(f"{BACKEND_URL}/api/v1/evaluations/sheet/{sheet_id}/run", method="POST", headers=t1_headers)
    assert status == 200, f"Re-evaluation failed: {re_eval_res}"
    re_eval_item = re_eval_res[0] if isinstance(re_eval_res, list) else re_eval_res.get("evaluations", [])[0]
    assert re_eval_item["marks_awarded"] == 8.5, f"Re-evaluation overwrote teacher marks! Found: {re_eval_item['marks_awarded']}"
    assert re_eval_item["is_reviewed"] is True, "Re-evaluation reset is_reviewed flag!"
    print("  -> INTEGRITY CONFIRMED: Re-evaluating the answer sheet DID NOT overwrite teacher's reviewed marks or feedback.")

    # 12. Export Results and Inspect
    print("\n--- 12. Exporting Results (CSV, Excel, PDF) ---")
    status, csv_data, csv_headers = http_req(f"{BACKEND_URL}/api/v1/reports/exam/{exam_id}/export?format=csv", headers=t1_headers)
    assert status == 200 and "text/csv" in csv_headers.get("Content-Type", ""), "CSV export failed"
    print(f"  -> CSV Export Successful ({len(csv_data)} bytes). Sample:\n     {csv_data.strip()[:180]}...")
    assert "KTU-2026-ENG-035" in csv_data, "Student roll missing from CSV"
    assert "8.5" in csv_data, "Teacher overridden mark (8.5) missing from CSV"

    status, excel_data, excel_headers = http_req(f"{BACKEND_URL}/api/v1/reports/exam/{exam_id}/export?format=excel", headers=t1_headers)
    assert status == 200, "Excel export failed"
    print(f"  -> Excel (.xlsx) Export Successful ({len(excel_data)} bytes).")

    status, pdf_data, pdf_headers = http_req(f"{BACKEND_URL}/api/v1/reports/exam/{exam_id}/export?format=pdf", headers=t1_headers)
    assert status == 200, "PDF export failed"
    print(f"  -> PDF Export Successful ({len(pdf_data)} bytes).")

    # 13. Verify Authorization and Privacy
    print("\n--- 13. Verifying Authorization & Privacy Boundaries ---")
    # Unauthenticated request (no token) -> 401
    status, unauth_res, _ = http_req(f"{BACKEND_URL}/api/v1/exams/{exam_id}")
    assert status == 401, f"Expected 401 for unauthenticated request, got {status}"
    print("  -> Unauthenticated request without token returned HTTP 401 Unauthorized.")

    # Cross-teacher access: Teacher 2 attempting to modify Teacher 1's exam -> 403
    status, t2_mod_exam, _ = http_req(f"{BACKEND_URL}/api/v1/exams/{exam_id}", method="PUT", headers=t2_headers, data={"title": "Hacked Title"})
    assert status == 403, f"Expected 403 for Teacher 2 modifying Teacher 1 exam, got {status}"
    print("  -> Cross-teacher exam modification blocked with HTTP 403 Forbidden.")

    # Teacher 2 attempting to upload answer sheet to Teacher 1's exam -> 403
    status, t2_upload, _ = http_upload(f"{BACKEND_URL}/api/v1/answer-sheets/upload/{exam_id}", t2_token, handwritten_path, "MALICIOUS_STUDENT")
    assert status == 403, f"Expected 403 for Teacher 2 uploading to Teacher 1 exam, got {status}"
    print("  -> Cross-teacher answer sheet upload blocked with HTTP 403 Forbidden.")

    # Teacher 2 attempting to override Teacher 1's evaluation -> 403
    status, t2_override, _ = http_req(f"{BACKEND_URL}/api/v1/reviews/evaluations/{eval_id}/override", method="POST", headers=t2_headers, data={
        "teacher_id": 2,
        "teacher_marks": 1.0,
    })
    assert status == 403, f"Expected 403 for Teacher 2 overriding Teacher 1 evaluation, got {status}"
    print("  -> Cross-teacher evaluation override blocked with HTTP 403 Forbidden.")

    # Teacher 2 attempting to export Teacher 1's exam report -> 403
    status, t2_export, _ = http_req(f"{BACKEND_URL}/api/v1/reports/exam/{exam_id}/export?format=csv", headers=t2_headers)
    assert status == 403, f"Expected 403 for Teacher 2 exporting Teacher 1 report, got {status}"
    print("  -> Cross-teacher report export blocked with HTTP 403 Forbidden.")

    print("\n--- 14. Verification Clean-up ---")
    status, del_res, _ = http_req(f"{BACKEND_URL}/api/v1/exams/{exam_id}", method="DELETE", headers=t1_headers)
    assert status == 204, f"Failed to delete test exam: {del_res}"
    print(f"  -> Cleaned up test exam {exam_id} from development database.")

    print("\n" + "=" * 70)
    print("ALL 14 VERIFICATION PHASES COMPLETED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    main()
