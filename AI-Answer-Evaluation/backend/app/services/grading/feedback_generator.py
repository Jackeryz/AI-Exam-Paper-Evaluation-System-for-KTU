"""Explainable Feedback Generator converting pre-computed score deductions into structured, human-readable feedback."""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.services.llm.llm_interface import get_llm_provider, LLMProvider
from app.services.grading.rubric_parser import ParsedRubric
from app.services.grading.score_aggregator import ScoreBreakdown, CriterionDeduction


class StructuredFeedback(BaseModel):
    """Structured feedback payload for student reports and teacher review."""
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    reasons_for_deduction: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    overall_summary: str = ""


class FeedbackGenerator:
    """Generates explainable, rubric-aware feedback strictly from pre-computed deductions (LLM NEVER modifies marks)."""

    SYSTEM_PROMPT = (
        "You are explaining an already-computed KTU Engineering examination grading result.\n"
        "RULES (CRITICAL - YOU MUST FOLLOW EXACTLY):\n"
        "1. Do NOT recalculate marks.\n"
        "2. Do NOT modify scores or invent new deductions.\n"
        "3. Use ONLY the provided pre-computed criterion-wise deductions to explain:\n"
        "   - what the student did correctly\n"
        "   - what was missing\n"
        "   - why marks were deducted\n"
        "   - how the answer can be improved\n"
        "4. Remain strictly faithful to the rubric sections.\n"
        "5. Output valid JSON matching this schema:\n"
        "{\n"
        '  "strengths": ["bullet point 1", "bullet point 2"],\n'
        '  "weaknesses": ["bullet point 1", "bullet point 2"],\n'
        '  "reasons_for_deduction": ["Lost X marks because..."],\n'
        '  "improvement_suggestions": ["Actionable suggestion 1"],\n'
        '  "overall_summary": "Summary paragraph."\n'
        "}"
    )

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self.llm_provider = llm_provider or get_llm_provider()

    async def generate_explainable_feedback(
        self,
        question_number: str,
        question_text: str,
        student_answer: str,
        ideal_answer: str,
        score_breakdown: ScoreBreakdown,
        parsed_rubric: ParsedRubric,
    ) -> StructuredFeedback:
        """Generate structured feedback from pre-computed score deductions."""
        deductions_str = "\n".join(
            f"- Criterion: {d.criterion} | Allocated: {d.allocated_marks} | Awarded: {d.awarded_marks} | Deducted: {d.deducted_marks} | Reason: {d.reason}"
            for d in score_breakdown.criterion_deductions
        )

        prompt = (
            f"Question {question_number}: {question_text}\n\n"
            f"Pre-Computed Marks: {score_breakdown.final_marks} / {score_breakdown.max_marks} ({score_breakdown.percentage}%)\n\n"
            f"Rubric Criteria & Pre-Computed Deductions:\n{deductions_str}\n\n"
            f"Student Answer:\n{student_answer}\n\n"
            f"Ideal Answer Reference:\n{ideal_answer}\n\n"
            "Generate the structured explainable feedback."
        )

        try:
            response = await self.llm_provider.generate(prompt=prompt, system_prompt=self.SYSTEM_PROMPT)
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            return StructuredFeedback(
                strengths=parsed.get("strengths", []),
                weaknesses=parsed.get("weaknesses", []),
                reasons_for_deduction=parsed.get("reasons_for_deduction", []),
                improvement_suggestions=parsed.get("improvement_suggestions", []),
                overall_summary=parsed.get("overall_summary", ""),
            )
        except Exception as exc:
            logger.info(f"Using rule-based feedback generator fallback ({exc}).")
            return self._rule_based_feedback(score_breakdown, parsed_rubric)

    def _rule_based_feedback(
        self,
        score_breakdown: ScoreBreakdown,
        parsed_rubric: ParsedRubric,
    ) -> StructuredFeedback:
        """Deterministic rule-based fallback built directly from CriterionDeduction objects."""
        strengths = []
        weaknesses = []
        deduction_reasons = []
        suggestions = []

        for d in score_breakdown.criterion_deductions:
            if d.deducted_marks <= 0.0:
                strengths.append(f"Full marks awarded for {d.criterion} ({d.awarded_marks}/{d.allocated_marks}).")
            elif d.awarded_marks > 0.0:
                weaknesses.append(f"Partial credit for {d.criterion} ({d.awarded_marks}/{d.allocated_marks}).")
                deduction_reasons.append(f"Lost {d.deducted_marks} mark(s) on {d.criterion}: {d.reason}")
                suggestions.append(f"Provide complete details for {d.criterion} to gain full marks.")
            else:
                weaknesses.append(f"No marks awarded for {d.criterion} (0/{d.allocated_marks}).")
                deduction_reasons.append(f"Lost {d.deducted_marks} mark(s) on {d.criterion}: Section was missing or incorrect.")
                suggestions.append(f"Include the required {d.criterion} section as defined in the rubric.")

        if not strengths:
            strengths.append("Basic attempt made on the question.")

        summary = (
            f"The answer scored {score_breakdown.final_marks}/{score_breakdown.max_marks} ({score_breakdown.percentage}%). "
            f"Total deductions: {round(score_breakdown.max_marks - score_breakdown.final_marks, 2)} mark(s) across rubric criteria."
        )

        return StructuredFeedback(
            strengths=strengths,
            weaknesses=weaknesses,
            reasons_for_deduction=deduction_reasons,
            improvement_suggestions=suggestions,
            overall_summary=summary,
        )
