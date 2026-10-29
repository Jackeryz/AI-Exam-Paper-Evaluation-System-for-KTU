"""Regression test suite for Authentication and Authorization RBAC guards.

Verifies:
1. Unauthenticated requests are rejected with 401 Unauthorized.
2. Cross-teacher access attempts (Teacher 2 accessing Teacher 1's exams/sheets) return 403 Forbidden.
3. System Administrator has access to all examination records.
"""

import pytest


def test_unauthenticated_requests_return_401(unauth_client):
    """Ensure protected endpoints return 401 when no bearer token is provided."""
    # List exams
    res1 = unauth_client.get("/api/v1/exams/")
    assert res1.status_code == 401
    assert "credentials" in res1.text.lower() or "not authenticated" in res1.text.lower()

    # Dashboard analytics
    res2 = unauth_client.get("/api/v1/analytics/dashboard")
    assert res2.status_code == 401

    # Pending reviews
    res3 = unauth_client.get("/api/v1/reviews/pending")
    assert res3.status_code == 401


def test_cross_teacher_isolation_returns_403(auth_client, teacher2_client):
    """Ensure Teacher 2 cannot view, edit, or delete Teacher 1's examination."""
    # Teacher 1 creates an exam
    ex_res = auth_client.post("/api/v1/exams/", json={
        "title": "Teacher 1 Private Exam",
        "subject": "Data Structures",
        "subject_code": "CST201",
        "max_marks": 50.0,
        "questions": [{
            "question_number": "1",
            "text": "Explain binary search tree insertion.",
            "max_marks": 10.0
        }]
    })
    assert ex_res.status_code == 201
    exam_id = ex_res.json()["id"]

    try:
        # Teacher 2 attempts to get exam details -> 403 Forbidden
        t2_get = teacher2_client.get(f"/api/v1/exams/{exam_id}")
        assert t2_get.status_code == 403
        assert "Not authorized" in t2_get.json()["detail"]

        # Teacher 2 attempts to configure questions -> 403 Forbidden
        t2_q = teacher2_client.post(f"/api/v1/exams/{exam_id}/questions", json=[{
            "question_number": "2",
            "text": "Malicious question addition",
            "max_marks": 10.0
        }])
        assert t2_q.status_code == 403

        # Teacher 2 attempts to delete Teacher 1's exam -> 403 Forbidden
        t2_del = teacher2_client.delete(f"/api/v1/exams/{exam_id}")
        assert t2_del.status_code == 403

        # Teacher 1 can access their own exam -> 200 OK
        t1_get = auth_client.get(f"/api/v1/exams/{exam_id}")
        assert t1_get.status_code == 200

    finally:
        # Teacher 1 cleans up
        auth_client.delete(f"/api/v1/exams/{exam_id}")


def test_admin_has_full_access_to_all_exams(auth_client, admin_client):
    """Ensure Administrator can view and manage any teacher's examination."""
    # Teacher 1 creates an exam
    ex_res = auth_client.post("/api/v1/exams/", json={
        "title": "Teacher 1 Exam For Admin Audit",
        "subject": "Operating Systems",
        "subject_code": "CST206",
        "max_marks": 50.0,
        "questions": [{
            "question_number": "1",
            "text": "Explain process scheduling algorithms.",
            "max_marks": 10.0
        }]
    })
    assert ex_res.status_code == 201
    exam_id = ex_res.json()["id"]

    try:
        # Admin accesses Teacher 1's exam -> 200 OK
        admin_get = admin_client.get(f"/api/v1/exams/{exam_id}")
        assert admin_get.status_code == 200
        assert admin_get.json()["id"] == exam_id

    finally:
        auth_client.delete(f"/api/v1/exams/{exam_id}")
