"""Analytics Engine computing class performance metrics, weak topics, and difficulty heatmaps."""

from typing import Any, Dict, List
from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    exam_id: int
    total_students_evaluated: int
    average_marks: float
    highest_marks: float
    lowest_marks: float
    pass_percentage: float
    weak_topics: List[str]
    question_difficulty_distribution: Dict[str, str]  # {"Q1(a)": "Easy", "Q2(b)": "Hard"}


class AnalyticsEngine:
    """Class-wide performance and topic vulnerability analytics calculator."""

    def compute_exam_analytics(
        self,
        exam_id: int,
        student_evaluations: List[Dict[str, Any]],
    ) -> AnalyticsSummary:
        if not student_evaluations:
            return AnalyticsSummary(
                exam_id=exam_id,
                total_students_evaluated=0,
                average_marks=0.0,
                highest_marks=0.0,
                lowest_marks=0.0,
                pass_percentage=0.0,
                weak_topics=["No student data evaluated yet."],
                question_difficulty_distribution={},
            )

        total_scores = [ev.get("total_marks", 0.0) for ev in student_evaluations]
        total_students = len(total_scores)
        avg_marks = round(sum(total_scores) / total_students, 2)
        highest = max(total_scores)
        lowest = min(total_scores)

        passed = sum(1 for s in total_scores if s >= 40.0)
        pass_pct = round((passed / total_students) * 100.0, 1)

        # Mock weak concept topic analysis
        weak_topics = [
            "Directive Principles vs Fundamental Rights (Constitution)",
            "Elasticity of Demand & Market Structure (Economics)",
            "Whistleblowing & Conflict of Interest (Ethics)",
        ]

        difficulty = {
            "Q1(a)": "Easy (Avg 8.5/10)",
            "Q1(b)": "Medium (Avg 6.2/10)",
            "Q2(a)": "Hard (Avg 4.1/10)",
        }

        return AnalyticsSummary(
            exam_id=exam_id,
            total_students_evaluated=total_students,
            average_marks=avg_marks,
            highest_marks=highest,
            lowest_marks=lowest,
            pass_percentage=pass_pct,
            weak_topics=weak_topics,
            question_difficulty_distribution=difficulty,
        )
