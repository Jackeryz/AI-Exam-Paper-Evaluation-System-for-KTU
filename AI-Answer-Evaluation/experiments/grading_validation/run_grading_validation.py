"""Grading Validation Runner against Synthetic Reference Labels.

Evaluates 22 controlled KTU-style student answers across 10 categories,
validates scoring invariants, calculates statistical metrics (MAE, RMSE,
exact agreement, tolerance agreement, criterion accuracy), and outputs
detailed reports.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import math
import os
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


async def run_validation() -> Dict[str, Any]:
    dataset_path = project_root / "experiments" / "grading_validation" / "synthetic_grading_dataset.json"
    output_dir = project_root / "experiments" / "grading_validation" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(cases)} synthetic validation cases from {dataset_path.name}.")
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
            "exact_match": abs_error == 0.0,
            "within_0_5": abs_error <= 0.5,
            "within_1_0": abs_error <= 1.0,
            "ai_confidence": grading_res.confidence_score,
            "is_flagged": grading_res.is_flagged,
            "criterion_comparisons": crit_comparisons,
            "ai_feedback_summary": grading_res.feedback,
            "human_rationale": rationale,
            "evaluation_latency_seconds": round(t_case, 3),
        }
        results.append(res_record)
        print(f"[{case_id}] {category[:35]:35s} | Human: {human_m:4.1f}/{max_m:4.1f} | AI: {ai_m:4.1f} | Diff: {raw_error:+5.2f} | Flagged: {grading_res.is_flagged}")

    total_time = time.perf_counter() - t0

    # ---------------------------------------------------------
    # Global Statistical Analysis
    # ---------------------------------------------------------
    n = len(results)
    mae = sum(r["abs_error"] for r in results) / n
    norm_mae_pct = sum(r["norm_abs_error_pct"] for r in results) / n
    mse = sum(r["raw_error"] ** 2 for r in results) / n
    rmse = math.sqrt(mse)
    norm_rmse_pct = math.sqrt(sum((r["norm_abs_error_pct"] / 100.0) ** 2 for r in results) / n) * 100.0

    exact_matches = sum(1 for r in results if r["exact_match"])
    within_0_5 = sum(1 for r in results if r["within_0_5"])
    within_1_0 = sum(1 for r in results if r["within_1_0"])

    exact_rate = round((exact_matches / n) * 100.0, 2)
    rate_0_5 = round((within_0_5 / n) * 100.0, 2)
    rate_1_0 = round((within_1_0 / n) * 100.0, 2)

    # ---------------------------------------------------------
    # Category-Wise Analysis
    # ---------------------------------------------------------
    categories = sorted(list(dict.fromkeys(r["category"] for r in results)))
    cat_summary = {}

    for cat in categories:
        cat_cases = [r for r in results if r["category"] == cat]
        k = len(cat_cases)
        c_mae = sum(r["abs_error"] for r in cat_cases) / k
        c_norm_mae = sum(r["norm_abs_error_pct"] for r in cat_cases) / k
        c_rmse = math.sqrt(sum(r["raw_error"] ** 2 for r in cat_cases) / k)
        c_exact = sum(1 for r in cat_cases if r["exact_match"])
        c_0_5 = sum(1 for r in cat_cases if r["within_0_5"])
        c_flagged = sum(1 for r in cat_cases if r["is_flagged"])

        cat_summary[cat] = {
            "case_count": k,
            "mae_marks": round(c_mae, 3),
            "norm_mae_pct": round(c_norm_mae, 2),
            "rmse_marks": round(c_rmse, 3),
            "exact_agreement_pct": round((c_exact / k) * 100.0, 2),
            "within_0_5_pct": round((c_0_5 / k) * 100.0, 2),
            "flagged_for_review_count": c_flagged,
            "flagged_rate_pct": round((c_flagged / k) * 100.0, 2),
        }

    # ---------------------------------------------------------
    # Invariant Validations
    # ---------------------------------------------------------
    # Invariant 1: Marks bounds [0, max_marks]
    bounds_check = all(0.0 <= r["ai_marks"] <= r["max_marks"] for r in results)
    
    # Invariant 2: Blank answers receive 0.0 marks
    blank_check = all(r["ai_marks"] == 0.0 for r in results if "Blank" in r["category"])
    
    # Invariant 3: Irrelevant answers receive 0.0 marks
    irrelevant_check = all(r["ai_marks"] == 0.0 for r in results if "irrelevant" in r["category"].lower())
    
    # Invariant 4: Alternative terminology receives substantial credit (>= 7.0/10)
    alt_term_check = all(r["ai_marks"] >= 7.0 for r in results if "alternative" in r["category"].lower())

    # Invariant 5: Formula spacing not penalized (Case 18 gets >= 4.0/5.0)
    formula_case = next(r for r in results if r["id"] == "CASE-18")
    formula_check = formula_case["ai_marks"] >= 4.0

    invariants = {
        "marks_within_zero_to_max": bounds_check,
        "blank_answers_receive_zero": blank_check,
        "irrelevant_content_receives_zero": irrelevant_check,
        "alternative_terminology_credited": alt_term_check,
        "formula_spacing_not_penalized": formula_check,
    }

    # ---------------------------------------------------------
    # Compile Summary Data
    # ---------------------------------------------------------
    summary = {
        "validation_metadata": {
            "timestamp": datetime.utcnow().isoformat(),
            "dataset_version": "KTU-Synthetic-v1.0",
            "total_cases_evaluated": n,
            "total_execution_time_seconds": round(total_time, 2),
            "average_latency_per_case_seconds": round(total_time / n, 2),
        },
        "aggregate_metrics": {
            "mean_absolute_error_marks": round(mae, 3),
            "normalized_mae_percentage": round(norm_mae_pct, 2),
            "root_mean_squared_error_marks": round(rmse, 3),
            "normalized_rmse_percentage": round(norm_rmse_pct, 2),
            "exact_mark_agreement_rate_pct": exact_rate,
            "within_0_5_marks_rate_pct": rate_0_5,
            "within_1_0_marks_rate_pct": rate_1_0,
        },
        "invariants_verification": invariants,
        "category_breakdown": cat_summary,
        "cases": results,
    }

    # Write output files
    with open(output_dir / "validation_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(output_dir / "category_metrics.json", "w", encoding="utf-8") as f:
        json.dump(cat_summary, f, indent=2)

    # Write CSV summary
    import csv
    with open(output_dir / "validation_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Case ID", "Category", "Subject", "Q#", "Max Marks",
            "Human Marks", "AI Marks", "Raw Error", "Abs Error",
            "Norm Error %", "Exact Match", "Within 0.5", "Flagged", "Latency (s)"
        ])
        for r in results:
            writer.writerow([
                r["id"], r["category"], r["subject"], r["question_number"],
                r["max_marks"], r["human_marks"], r["ai_marks"],
                r["raw_error"], r["abs_error"], r["norm_abs_error_pct"],
                r["exact_match"], r["within_0_5"], r["is_flagged"], r["evaluation_latency_seconds"]
            ])

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total Cases Evaluated:       {n}")
    print(f"Mean Absolute Error (MAE):   {mae:.3f} marks (Normalized: {norm_mae_pct:.2f}%)")
    print(f"Root Mean Squared Error:     {rmse:.3f} marks (Normalized: {norm_rmse_pct:.2f}%)")
    print(f"Exact Agreement Rate:        {exact_rate:.2f}% ({exact_matches}/{n})")
    print(f"Agreement within 0.5 marks:  {rate_0_5:.2f}% ({within_0_5}/{n})")
    print(f"Agreement within 1.0 mark:   {rate_1_0:.2f}% ({within_1_0}/{n})")
    print(f"Invariants Check:            {all(invariants.values())}")
    for inv, ok in invariants.items():
        print(f"  - {inv}: {'PASS' if ok else 'FAIL'}")
    print(f"Artifacts saved to: {output_dir}")

    return summary


if __name__ == "__main__":
    asyncio.run(run_validation())
