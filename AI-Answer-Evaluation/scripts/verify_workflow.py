"""Verification script testing Examination and Export lifecycle."""
import requests

BASE = "http://127.0.0.1:8000/api/v1"

payload = {
    "title": "KTU S5 Engineering Economics",
    "subject": "Engineering Economics",
    "subject_code": "HUT300",
    "semester": "S5",
    "academic_year": "2024-2025",
    "exam_type": "Regular End-Semester",
    "max_marks": 50.0,
    "duration_minutes": 120,
    "instructions": "Attempt all questions with step-by-step calculations.",
    "questions": [
        {"question_number": "1(a)", "text": "Explain Time Value of Money with Cash Flow Diagram.", "max_marks": 25.0},
        {"question_number": "1(b)", "text": "Calculate Net Present Value (NPV) for given cash flows.", "max_marks": 25.0}
    ]
}

# 1. Create exam
r1 = requests.post(f"{BASE}/exams", json=payload)
print(f"1. Create Exam: HTTP {r1.status_code}, Exam Code: {r1.json().get('exam_code')}")
assert r1.status_code == 201
exam = r1.json()
exam_id = exam["id"]

# 2. Update exam metadata
r2 = requests.put(f"{BASE}/exams/{exam_id}", json={"instructions": "Updated: Non-programmable calculators allowed."})
print(f"2. Update Exam: HTTP {r2.status_code}, Instructions: {r2.json().get('instructions')}")
assert r2.status_code == 200
assert "Non-programmable" in r2.json()["instructions"]

# 3. Test Export endpoints
for fmt in ["csv", "excel", "pdf"]:
    exp_r = requests.get(f"{BASE}/reports/exam/{exam_id}/export?format={fmt}")
    print(f"3. Export {fmt.upper()}: HTTP {exp_r.status_code}, Content-Type: {exp_r.headers.get('content-type')}, Size: {len(exp_r.content)} bytes")
    assert exp_r.status_code == 200
    assert len(exp_r.content) > 0

# 4. Clean up after verification
del_r = requests.delete(f"{BASE}/exams/{exam_id}")
print(f"4. Delete Exam: HTTP {del_r.status_code}")
assert del_r.status_code == 204

print("\nAll lifecycle operations verified successfully!")
