"""Runner for Version 2 Evaluation Benchmark (25 test cases across 5 KTU subjects)."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

# Setup project root and python path
project_root = Path(__file__).resolve().parents[2]
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.services.grading.evaluator import EvaluatorOrchestrator


async def run_benchmark_v2() -> Dict[str, Any]:
    dataset_path = project_root / "experiments" / "grading_validation" / "evaluation_benchmark_v2.json"
    output_dir = project_root / "experiments" / "grading_validation" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(cases)} validation cases from {dataset_path.name}.")
    orchestrator = EvaluatorOrchestrator()

    results: List[Dict[str, Any]] = []
    t0 = time.perf_counter()

    for idx, c in enumerate(cases):
        case_id = c["id"]
        category = c["category"]
        q_num = c["question_number"]
        q_text = c["question_text"]
        max_m = float(c["max_marks"])
        ideal = c["ideal_answer"]
        rubric = c["rubric"]
        student_ans = c["student_answer"]
        human_m = float(c["human_marks"])
        human_crit = c.get("human_criterion_marks", {})
        rationale = c.get("human_rationale", "")

        t_case_start = time.perf_counter()
        grading_res = await orchestrator.evaluate(
            question_number=q_num,
            question_text=q_text,
            student_answer=student_ans,
            ideal_answer=ideal,
            rubric_data=rubric,
            max_marks=max_m,
            ocr_confidence=0.90,
        )
        t_case = time.perf_counter() - t_case_start

        ai_m = float(grading_res.marks_awarded)
        raw_error = round(ai_m - human_m, 3)
        abs_error = round(abs(ai_m - human_m), 3)
        norm_abs_error_pct = round((abs_error / max_m) * 100.0, 2) if max_m > 0 else 0.0

        # Criterion-level comparison
        crit_comparisons = []
        for cd in grading_res.criterion_deductions:
            h_crit_val = human_crit.get(cd.criterion, None)
            c_diff = round(abs(cd.awarded_marks - h_crit_val), 3) if h_crit_val is not None else None
            crit_comparisons.append({
                "criterion": cd.criterion,
                "allocated": cd.allocated_marks,
                "ai_awarded": cd.awarded_marks,
                "human_awarded": h_crit_val,
                "ai_deducted": cd.deducted_marks,
                "abs_diff": c_diff,
                "reason": cd.reason,
                "evidence": cd.evidence,
            })

        res_record = {
            "id": case_id,
            "category": category,
            "subject": c["subject"],
            "question_number": q_num,
            "max_marks": max_m,
            "human_marks": human_m,
            "ai_marks": ai_m,
            "raw_error": raw_error,
            "abs_error": abs_error,
            "norm_abs_error_pct": norm_abs_error_pct,
            "confidence_score": grading_res.confidence_score,
            "is_flagged": grading_res.is_flagged,
            "evaluation_method": grading_res.evaluation_method,
            "contradictions": grading_res.identified_contradictions,
            "criterion_deductions": crit_comparisons,
            "feedback": grading_res.feedback,
            "improvement_suggestions": grading_res.improvement_suggestions,
            "human_rationale": rationale,
            "latency_seconds": round(t_case, 3),
        }
        results.append(res_record)

        print(
            f"[{case_id}] {category[:30]:30} | Human: {human_m:4.1f}/{max_m:<4.1f} | "
            f"AI: {ai_m:4.1f} | Diff: {raw_error:+5.2f} | Flagged: {grading_res.is_flagged}"
        )

    total_time = time.perf_counter() - t0
    n = len(results)

    # Statistical Aggregates
    mae = sum(r["abs_error"] for r in results) / n
    rmse = math.sqrt(sum(r["raw_error"] ** 2 for r in results) / n)
    exact_agreements = sum(1 for r in results if r["abs_error"] == 0.0)
    agreements_0_5 = sum(1 for r in results if r["abs_error"] <= 0.5)
    agreements_1_0 = sum(1 for r in results if r["abs_error"] <= 1.0)
    agreements_1_5 = sum(1 for r in results if r["abs_error"] <= 1.5)

    # Invariant checks
    bounds_ok = all(0.0 <= r["ai_marks"] <= r["max_marks"] for r in results)
    blank_cases = [r for r in results if "Blank" in r["category"] or "Whitespace" in r["category"]]
    blank_ok = all(r["ai_marks"] == 0.0 and r["is_flagged"] for r in blank_cases)
    irrelevant_cases = [r for r in results if "irrelevant" in r["category"].lower()]
    irrelevant_ok = all(r["ai_marks"] == 0.0 for r in irrelevant_cases)

    summary = {
        "benchmark_version": "v2",
        "timestamp": datetime.utcnow().isoformat(),
        "total_cases": n,
        "total_runtime_seconds": round(total_time, 2),
        "mean_absolute_error": round(mae, 3),
        "root_mean_squared_error": round(rmse, 3),
        "exact_agreement_count": exact_agreements,
        "exact_agreement_rate": round((exact_agreements / n) * 100.0, 2),
        "within_0_5_marks_count": agreements_0_5,
        "within_0_5_marks_rate": round((agreements_0_5 / n) * 100.0, 2),
        "within_1_0_marks_count": agreements_1_0,
        "within_1_0_marks_rate": round((agreements_1_0 / n) * 100.0, 2),
        "within_1_5_marks_count": agreements_1_5,
        "within_1_5_marks_rate": round((agreements_1_5 / n) * 100.0, 2),
        "invariants": {
            "all_marks_within_bounds": bounds_ok,
            "blank_answers_zero_and_flagged": blank_ok,
            "irrelevant_content_zero": irrelevant_ok,
        },
        "detailed_results": results,
    }

    out_file = output_dir / "benchmark_v2_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 60)
    print("BENCHMARK V2 VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total Cases Evaluated:       {n}")
    print(f"Mean Absolute Error (MAE):   {mae:.3f} marks")
    print(f"Root Mean Squared Error:     {rmse:.3f} marks")
    print(f"Exact Agreement Rate:        {summary['exact_agreement_rate']}% ({exact_agreements}/{n})")
    print(f"Agreement within 0.5 marks:  {summary['within_0_5_marks_rate']}% ({agreements_0_5}/{n})")
    print(f"Agreement within 1.0 mark:   {summary['within_1_0_marks_rate']}% ({agreements_1_0}/{n})")
    print(f"Invariants Check:            {bounds_ok and blank_ok and irrelevant_ok}")
    print(f"  - marks_within_zero_to_max: {'PASS' if bounds_ok else 'FAIL'}")
    print(f"  - blank_answers_receive_zero: {'PASS' if blank_ok else 'FAIL'}")
    print(f"  - irrelevant_content_receives_zero: {'PASS' if irrelevant_ok else 'FAIL'}")
    print(f"Artifacts saved to: {out_file.resolve()}")

    return summary


if __name__ == "__main__":
    asyncio.run(run_benchmark_v2())
