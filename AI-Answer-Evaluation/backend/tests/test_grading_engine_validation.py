"""Unit and regression tests for KTU AI Grading Engine.

Validates scoring invariants, blank/irrelevant input handling, formula and unit formatting,
alternative valid terminology, and teacher audit persistence using isolated test fixtures.
"""

import json
from pathlib import Path
import pytest

from app.services.grading.evaluator import EvaluatorOrchestrator
from app.services.grading.grading_metrics import GradingMetrics
from app.services.grading.keyword_extractor import KeywordExtractor
from app.services.grading.rubric_parser import ParsedRubric, RubricSection


@pytest.fixture
def grading_orchestrator():
    return EvaluatorOrchestrator()


@pytest.mark.anyio
async def test_blank_answers_receive_zero_and_flagged(grading_orchestrator):
    """Ensure blank or whitespace answers receive exactly 0.0 marks and are flagged for review."""
    rubric = {
        "sections": {
            "Statement of Law": 2.0,
            "Formula": 1.5,
            "Calculation": 1.5,
        },
        "mandatory_keywords": ["Ohm's Law", "V = IR", "40 Watts"]
    }
    
    # Test completely empty
    res_empty = await grading_orchestrator.evaluate(
        question_number="1",
        question_text="State Ohm's Law and calculate power",
        student_answer="",
        ideal_answer="Ohm's Law states V = IR.",
        rubric_data=rubric,
        max_marks=5.0,
    )
    assert res_empty.score_breakdown.final_marks == 0.0
    assert res_empty.is_flagged is True
    assert all(d.awarded_marks == 0.0 for d in res_empty.score_breakdown.criterion_deductions)

    # Test whitespace-only
    res_ws = await grading_orchestrator.evaluate(
        question_number="1",
        question_text="State Ohm's Law and calculate power",
        student_answer="   \n\t  ",
        ideal_answer="Ohm's Law states V = IR.",
        rubric_data=rubric,
        max_marks=5.0,
    )
    assert res_ws.score_breakdown.final_marks == 0.0
    assert res_ws.is_flagged is True


@pytest.mark.anyio
async def test_irrelevant_answers_receive_zero_marks(grading_orchestrator):
    """Ensure off-topic content receives zero marks and is flagged for review."""
    rubric = {
        "sections": {
            "Basic Structure Principle": 5.0,
            "Article 368 Limitation": 5.0,
        },
        "mandatory_keywords": ["Kesavananda Bharati", "Basic Structure", "Article 368"]
    }
    irrelevant_text = (
        "Mitochondria is the powerhouse of the cell. Cellular respiration generates ATP "
        "through the electron transport chain inside the inner mitochondrial membrane."
    )
    res = await grading_orchestrator.evaluate(
        question_number="1(a)",
        question_text="Explain the Basic Structure Doctrine.",
        student_answer=irrelevant_text,
        ideal_answer="In Kesavananda Bharati, the Supreme Court ruled Parliament cannot alter the basic structure.",
        rubric_data=rubric,
        max_marks=10.0,
    )
    assert res.score_breakdown.final_marks == 0.0
    assert res.is_flagged is True


@pytest.mark.anyio
async def test_formula_and_unit_normalization(grading_orchestrator):
    """Ensure mathematical answers with spacing differences and SI unit symbols receive credit."""
    rubric = {
        "sections": {
            "Statement of Ohm's Law & Formula": 2.0,
            "Power Dissipation Formula Selection": 1.5,
            "Correct Numerical Calculation & Units": 1.5,
        },
        "mandatory_keywords": ["Ohm's Law", "V = IR", "constant temperature", "P = I^2 R", "40 Watts"]
    }
    ideal = "Ohm's Law states that V = IR at constant temperature. The power dissipated is P = I^2 R = 40 Watts."
    
    # Student answer using compact symbols (Ω, W, ^2, *) and no spaces in equations
    student_answer = (
        "Ohm's law: At constant temperature, V=I*R. Given R=10Ω, I=2A. "
        "Power dissipated P=I^2*R = (2A)^2 * (10Ω) = 4 * 10 = 40W."
    )
    res = await grading_orchestrator.evaluate(
        question_number="3",
        question_text="State Ohm's Law and calculate power dissipated in a 10 ohm resistor at 2A.",
        student_answer=student_answer,
        ideal_answer=ideal,
        rubric_data=rubric,
        max_marks=5.0,
    )
    # Must receive at least 4.0 out of 5.0 marks (>= 80%)
    assert res.score_breakdown.final_marks >= 4.0
    assert 0.0 <= res.score_breakdown.final_marks <= 5.0


@pytest.mark.anyio
async def test_alternative_terminology_credit(grading_orchestrator):
    """Ensure answers employing valid technical synonyms are appropriately credited."""
    rubric = {
        "sections": {
            "Basic Structure Principle & Landmark Case": 3.0,
            "Limitation on Article 368 Amending Power": 4.0,
            "Significance & Preservation of Judicial Review": 3.0,
        },
        "mandatory_keywords": ["Kesavananda Bharati", "Basic Structure", "Article 368", "judicial review"]
    }
    ideal = (
        "In Kesavananda Bharati v. State of Kerala (1973), the Supreme Court ruled that while Parliament "
        "possesses broad constituent powers under Article 368 to amend the Constitution, it cannot alter, "
        "destroy, or emasculate the Basic Structure or essential framework of the Constitution."
    )
    
    student_synonyms = (
        "The fundamental framework canon was articulated by the apex judiciary in the 1973 Kesavananda adjudication. "
        "The constitutional bench ruled that although the national legislature holds revising authority pursuant to "
        "Article 368, such jurisdiction cannot abrogate the irreducible core principles. Indispensable components "
        "comprise supervisory scrutiny by courts."
    )
    res = await grading_orchestrator.evaluate(
        question_number="1(a)",
        question_text="Explain the Basic Structure Doctrine and its significance.",
        student_answer=student_synonyms,
        ideal_answer=ideal,
        rubric_data=rubric,
        max_marks=10.0,
    )
    # Must receive substantial credit (>= 7.0 / 10.0)
    assert res.score_breakdown.final_marks >= 7.0
    assert 0.0 <= res.score_breakdown.final_marks <= 10.0


def test_grading_metrics_formula_normalization():
    """Verify operator-level and unit-level normalization directly in GradingMetrics."""
    student_text = "V=I*R and P=I^2*R with 40W and 10Ω"
    keywords = ["V = IR", "P = I^2 R", "40 Watts", "10 ohms"]
    synonyms = {
        "watts": ["w", "watt", "watts", "kw"],
        "ohms": ["ohm", "ohms", "Ω"],
        "v = ir": ["v=ir", "v=i*r", "v = i*r"],
        "p = i^2 r": ["p=i^2*r", "p=i^2r", "p = i^2 * r"],
    }
    coverage = GradingMetrics.keyword_coverage(student_text, keywords, synonyms)
    assert coverage == 1.0


def test_section_coverage_robustness():
    """Verify section coverage correctly identifies mathematical solutions without requiring literal keywords."""
    sections = [
        "Statement of Ohm's Law & Formula",
        "Power Dissipation Formula Selection",
        "Correct Numerical Calculation & Units",
    ]
    student_text = "Ohm's law: At constant temperature, V=I*R. Given R=10Ω, I=2A. Power dissipated P=I^2*R = (2A)^2 * (10Ω) = 4 * 10 = 40W."
    cov = GradingMetrics.section_coverage_ratio(student_text, sections)
    assert cov == 1.0


def test_teacher_review_and_override_audit_persistence(auth_client):
    """Ensure teacher overrides create audit records and survive subsequent re-evaluations."""
    # 1. Create test exam
    ex_res = auth_client.post("/api/v1/exams/", json={
        "title": "Grading Engine Audit Test Exam",
        "subject": "Basic Electrical Engineering",
        "subject_code": "EST100",
        "max_marks": 5.0,
        "questions": [{
            "question_number": "1",
            "text": "State Ohm's Law and calculate power dissipated.",
            "max_marks": 5.0
        }]
    })
    assert ex_res.status_code == 201
    exam_id = ex_res.json()["id"]
    q_id = ex_res.json()["questions"][0]["id"]

    try:
        # 2. Approve reference answer and rubric
        appr_res = auth_client.post(f"/api/v1/reference-answers/question/{q_id}/approve", json={
            "ideal_answer": "Ohm's Law states that V = IR at constant temperature. Power is P = I^2 R = 40 Watts.",
            "rubric_criteria": [
                {"criterion": "Statement & Formula", "allocated_marks": 2.5},
                {"criterion": "Numerical Calculation", "allocated_marks": 2.5}
            ]
        })
        assert appr_res.status_code == 200

        # 3. Upload answer sheet
        sample_path = Path("experiments/ocr_sandbox/input/handwritten/IMG-20260804-WA0035 - Krishnendu P B.jpg")
        with open(sample_path, "rb") as f:
            up_res = auth_client.post(
                f"/api/v1/answer-sheets/upload/{exam_id}",
                files={"files": (sample_path.name, f, "image/jpeg")},
                data={"student_identifier": "TEST_AUDIT_STUDENT"}
            )
        assert up_res.status_code == 201
        sheet_id = up_res.json()[0]["id"] if isinstance(up_res.json(), list) else up_res.json()["sheets"][0]["id"]

        # 4. Process OCR
        ocr_res = auth_client.post(f"/api/v1/answer-sheets/{sheet_id}/process-ocr")
        assert ocr_res.status_code == 200, f"OCR failed: {ocr_res.text}"

        # 5. Teacher approves specific corrected OCR text
        patch_res = auth_client.put(f"/api/v1/answer-sheets/{sheet_id}/ocr-correction", json={
            "corrected_text": "1. V=I*R and P=I^2*R. R=10 ohms, I=2A. Power is 40W."
        })
        assert patch_res.status_code == 200

        # 6. Run initial evaluation
        eval_res = auth_client.post(f"/api/v1/evaluations/sheet/{sheet_id}/run")
        assert eval_res.status_code == 200
        evals = eval_res.json() if isinstance(eval_res.json(), list) else eval_res.json().get("evaluations", [])
        assert len(evals) > 0
        target_eval = evals[0]
        initial_ai_marks = target_eval["marks_awarded"]

        # 7. Apply teacher override with human mark and recorded rationale
        teacher_override_mark = 4.75
        override_res = auth_client.post(f"/api/v1/reviews/evaluations/{target_eval['id']}/override", json={
            "teacher_marks": teacher_override_mark,
            "teacher_feedback": "Accurate derivation with clear units, human review accepted.",
            "comments": "Audited by KTU senior examiner"
        })
        assert override_res.status_code == 200
        assert override_res.json()["marks_awarded"] == teacher_override_mark
        assert override_res.json()["is_reviewed"] is True
        assert override_res.json()["is_flagged"] is False

        # 8. Re-run evaluation on the answer sheet (simulating re-evaluation)
        re_eval_res = auth_client.post(f"/api/v1/evaluations/sheet/{sheet_id}/run")
        assert re_eval_res.status_code == 200
        re_evals = re_eval_res.json() if isinstance(re_eval_res.json(), list) else re_eval_res.json().get("evaluations", [])
        re_target = re_evals[0]

        # Invariant: Re-evaluation MUST NOT overwrite teacher reviewed mark or teacher decision!
        assert re_target["marks_awarded"] == teacher_override_mark
        assert re_target["is_reviewed"] is True
        assert "Accurate derivation" in re_target["feedback"]
        assert "V=I*R and P=I^2*R" in re_target["student_answer_text"]

    finally:
        auth_client.delete(f"/api/v1/exams/{exam_id}")


@pytest.mark.anyio
async def test_concise_correct_answers_not_penalized(grading_orchestrator):
    """Ensure concise answers adequately addressing the question are not penalized for brevity."""
    rubric = {
        "sections": {
            "Definition & Law": 2.5,
            "Formula & Units": 2.5,
        },
        "mandatory_keywords": ["Ohm's Law", "V = IR", "constant temperature"]
    }
    ideal_verbose = (
        "Ohm's Law is a fundamental law in electrical engineering formulated by Georg Simon Ohm. "
        "It states that the electric current flowing through a conductor between two points is directly "
        "proportional to the voltage across the two points, provided the physical conditions and temperature "
        "remain constant. The mathematical equation describing this relationship is V = I * R, where V is voltage "
        "in volts, I is current in amperes, and R is electrical resistance in ohms. It forms the foundation of circuit analysis."
    )
    # Concise 18-word direct answer containing all principles
    student_concise = "At constant temperature, current is directly proportional to voltage: V = IR, where R is resistance in ohms."

    res = await grading_orchestrator.evaluate(
        question_number="1",
        question_text="State Ohm's Law and its mathematical formula.",
        student_answer=student_concise,
        ideal_answer=ideal_verbose,
        rubric_data=rubric,
        max_marks=5.0,
    )
    # Must receive substantial credit without being crushed by brevity penalty
    assert res.score_breakdown.final_marks >= 4.0
    assert res.research_metrics.length_normalization_ratio >= 0.85
    assert not res.is_flagged


@pytest.mark.anyio
async def test_contradictory_and_negated_claims_penalized_and_flagged(grading_orchestrator):
    """Ensure answers asserting factual contradictions or inverted relationships are penalized and flagged."""
    rubric = {
        "sections": {
            "Basic Structure Principle": 5.0,
            "Limitation on Article 368": 5.0,
        },
        "mandatory_keywords": ["Kesavananda Bharati", "Article 368", "Basic Structure"]
    }
    ideal_const = (
        "In Kesavananda Bharati v. State of Kerala (1973), the Supreme Court ruled that Article 368 does not "
        "grant Parliament unlimited power. Parliament cannot alter or destroy the basic structure of the Constitution, "
        "and constitutional amendments remain subject to judicial review."
    )
    # Student answer with high keyword presence but asserting the exact opposite (contradiction)
    contradictory_answer = (
        "Under Article 368 and Kesavananda Bharati, Parliament possesses absolute and unlimited power to amend "
        "any part of the Constitution without limitation by judicial review. Parliament can alter the basic structure."
    )

    res = await grading_orchestrator.evaluate(
        question_number="1(a)",
        question_text="Explain the Basic Structure Doctrine and limitations under Article 368.",
        student_answer=contradictory_answer,
        ideal_answer=ideal_const,
        rubric_data=rubric,
        max_marks=10.0,
    )
    # Invariant: Must identify contradictions, penalize score, and flag for teacher review
    assert len(res.identified_contradictions) > 0
    assert any("Basic Structure Doctrine" in c or "without limitation" in c for c in res.identified_contradictions)
    assert res.is_flagged is True
    # Correctness score must be significantly lower than an accurate answer
    assert res.score_breakdown.correctness_score <= 4.0


@pytest.mark.anyio
async def test_criterion_wise_breakdown_and_evaluation_method_reporting(grading_orchestrator):
    """Ensure evaluation results expose criterion deductions, points addressed, and truthful methodology."""
    rubric = {
        "sections": {
            "Law Definition": 2.0,
            "Assumptions": 3.0,
            "Exceptions": 5.0,
        },
        "mandatory_keywords": ["inverse relationship", "ceteris paribus", "Giffen goods"]
    }
    ideal = (
        "The Law of Demand states that price and quantity demanded have an inverse relationship, "
        "ceteris paribus (other factors constant). Exceptions include Giffen goods, Veblen luxury goods, and emergencies."
    )
    # Student states definition and assumptions, but omits exceptions
    student_partial = (
        "Law of Demand: Price and quantity demanded share an inverse relationship under ceteris paribus "
        "(consumer income, tastes, and other factors remain constant)."
    )

    res = await grading_orchestrator.evaluate(
        question_number="2(a)",
        question_text="State the Law of Demand with assumptions and exceptions.",
        student_answer=student_partial,
        ideal_answer=ideal,
        rubric_data=rubric,
        max_marks=10.0,
    )

    # 1. Methodology truthfulness: Offline fallback must be truthfully declared
    assert res.evaluation_method in ["DETERMINISTIC_HEURISTIC_FALLBACK", "LOCAL_LLM", "OLLAMA_LLM"]
    if res.evaluation_method == "DETERMINISTIC_HEURISTIC_FALLBACK":
        assert "fallback" in res.reasons_for_grading.lower() or "deterministic" in res.reasons_for_grading.lower()

    # 2. Points addressed and missing points populated
    assert len(res.points_addressed) > 0
    assert len(res.missing_points) > 0
    assert any("exceptions" in m.lower() for m in res.missing_points)

    # 3. Criterion deductions populated with individual allocated and deducted marks
    assert len(res.criterion_deductions) == 3
    sec_names = [cd.criterion for cd in res.criterion_deductions]
    assert "Law Definition" in sec_names
    assert "Exceptions" in sec_names


@pytest.mark.anyio
async def test_mark_bounds_and_criterion_total_consistency(grading_orchestrator):
    """Ensure final marks and criterion-wise totals are strictly bounded between 0 and max_marks."""
    rubric = {
        "sections": {
            "Principle": 3.0,
            "Derivation": 4.0,
            "Application": 3.0,
        }
    }
    for ans in [
        "",  # blank
        "random irrelevant gibberish xyz abc",  # irrelevant
        "Accurate principle and derivation with complete application steps.",  # correct
        "Principle only.",  # partial
    ]:
        res = await grading_orchestrator.evaluate(
            question_number="1",
            question_text="State principle and derivation.",
            student_answer=ans,
            ideal_answer="Accurate principle and derivation with complete application steps.",
            rubric_data=rubric,
            max_marks=10.0,
        )
        assert 0.0 <= res.marks_awarded <= 10.0
        assert 0.0 <= res.percentage <= 100.0
        # Criterion total consistency
        if res.criterion_deductions:
            total_allocated = sum(d.allocated_marks for d in res.criterion_deductions)
            assert abs(total_allocated - 10.0) <= 0.1
            total_awarded = sum(d.awarded_marks for d in res.criterion_deductions)
            assert total_awarded <= 10.0


