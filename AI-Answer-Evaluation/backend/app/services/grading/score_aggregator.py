"""Deterministic Score Aggregator computing final marks and criterion-wise deductions."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import logger
from app.services.grading.rubric_parser import ParsedRubric


class CriterionDeduction(BaseModel):
    """Detailed criterion-wise mark allocation, award, deduction, and explanation."""
    criterion: str
    allocated_marks: float
    awarded_marks: float
    deducted_marks: float
    reason: str
    evidence: Optional[str] = None


class ScoreWeights(BaseModel):
    concept_weight: float = 0.30
    correctness_weight: float = 0.20
    completeness_weight: float = 0.20
    keyword_weight: float = 0.10
    semantic_weight: float = 0.20


class ScoreBreakdown(BaseModel):
    concept_score: float         # 0.0 to 10.0
    correctness_score: float     # 0.0 to 10.0
    completeness_score: float    # 0.0 to 10.0
    keyword_score: float         # 0.0 to 10.0
    semantic_score: float        # 0.0 to 10.0
    final_marks: float           # 0.0 to max_marks
    max_marks: float
    percentage: float            # 0.0 to 100.0
    weights_used: Dict[str, float]
    criterion_deductions: List[CriterionDeduction] = Field(default_factory=list)


class ScoreAggregator:
    """Computes deterministic final marks and generates criterion-wise deductions."""

    def __init__(self, custom_weights: Optional[ScoreWeights] = None) -> None:
        settings = get_settings()
        if custom_weights:
            self.weights = custom_weights
        else:
            self.weights = ScoreWeights(
                concept_weight=settings.CONCEPT_WEIGHT,
                correctness_weight=settings.CORRECTNESS_WEIGHT,
                completeness_weight=settings.COMPLETENESS_WEIGHT,
                keyword_weight=settings.KEYWORD_WEIGHT,
                semantic_weight=settings.SEMANTIC_WEIGHT,
            )

    def aggregate(
        self,
        concept_score: float,      # 0 to 10 scale
        correctness_score: float,  # 0 to 10 scale
        completeness_score: float, # 0 to 10 scale
        keyword_coverage: float,   # 0.0 to 1.0 ratio
        semantic_similarity: float,# 0.0 to 1.0 ratio
        parsed_rubric: Optional[ParsedRubric] = None,
        max_marks: float = 10.0,
        section_performance: Optional[Dict[str, float]] = None,
        section_evidence: Optional[Dict[str, Optional[str]]] = None,
    ) -> ScoreBreakdown:
        """Compute final marks deterministically and produce criterion-wise deductions."""
        # Convert ratios to 0-10 scale
        kw_score_10 = max(0.0, min(10.0, keyword_coverage * 10.0))
        sem_score_10 = max(0.0, min(10.0, semantic_similarity * 10.0))
        c_score_10 = max(0.0, min(10.0, concept_score))
        corr_score_10 = max(0.0, min(10.0, correctness_score))
        comp_score_10 = max(0.0, min(10.0, completeness_score))

        # Weighted aggregate score (0 to 10 scale)
        weighted_score_10 = (
            (c_score_10 * self.weights.concept_weight) +
            (corr_score_10 * self.weights.correctness_weight) +
            (comp_score_10 * self.weights.completeness_weight) +
            (kw_score_10 * self.weights.keyword_weight) +
            (sem_score_10 * self.weights.semantic_weight)
        )

        # Scale to max_marks
        final_marks = float(round((weighted_score_10 / 10.0) * max_marks, 2))
        percentage = float(round((final_marks / max_marks) * 100.0, 2)) if max_marks > 0 else 0.0

        weights_dict = {
            "concept": self.weights.concept_weight,
            "correctness": self.weights.correctness_weight,
            "completeness": self.weights.completeness_weight,
            "keyword": self.weights.keyword_weight,
            "semantic": self.weights.semantic_weight,
        }

        # Build Criterion-wise Deductions
        deductions: List[CriterionDeduction] = []

        if parsed_rubric and parsed_rubric.sections:
            # Distribute marks per section according to parsed rubric
            total_rubric_marks = sum(s.allocated_marks for s in parsed_rubric.sections) or max_marks
            scale_factor = max_marks / total_rubric_marks

            base_ratio = max(0.0, min(1.0, weighted_score_10 / 10.0))

            for sec in parsed_rubric.sections:
                sec_allocated = round(sec.allocated_marks * scale_factor, 2)
                # Section awarded score based on calibrated weighted performance ratio
                if section_performance and sec.name in section_performance:
                    sec_ratio = max(0.0, min(1.0, section_performance[sec.name]))
                else:
                    sec_ratio = base_ratio

                sec_awarded = round(sec_allocated * sec_ratio, 2)
                sec_deducted = round(sec_allocated - sec_awarded, 2)
                sec_ev = section_evidence.get(sec.name) if section_evidence else None

                if sec_deducted <= 0.0:
                    reason = f"{sec.name} criteria fully met."
                elif sec_awarded > 0.0:
                    reason = f"{sec.name} was partially addressed; required explanations or key concepts were incomplete."
                else:
                    reason = f"{sec.name} section was missing, omitted, or incorrect."

                deductions.append(
                    CriterionDeduction(
                        criterion=sec.name,
                        allocated_marks=sec_allocated,
                        awarded_marks=sec_awarded,
                        deducted_marks=sec_deducted,
                        reason=reason,
                        evidence=sec_ev,
                    )
                )

            # Ensure final_marks perfectly matches sum of criterion deductions
            sum_awarded = sum(d.awarded_marks for d in deductions)
            final_marks = float(round(min(max_marks, max(0.0, sum_awarded)), 2))
            percentage = float(round((final_marks / max_marks) * 100.0, 2)) if max_marks > 0 else 0.0
        else:
            # Default Categories: Concept, Correctness, Completeness, Keyword Coverage, Semantic Similarity
            cat_allocations = [
                ("Concept Understanding", self.weights.concept_weight * max_marks, c_score_10 / 10.0),
                ("Correctness", self.weights.correctness_weight * max_marks, corr_score_10 / 10.0),
                ("Completeness", self.weights.completeness_weight * max_marks, comp_score_10 / 10.0),
                ("Keyword Coverage", self.weights.keyword_weight * max_marks, keyword_coverage),
                ("Semantic Similarity", self.weights.semantic_weight * max_marks, semantic_similarity),
            ]

            for cat_name, alloc, ratio in cat_allocations:
                alloc_m = round(alloc, 2)
                award_m = round(alloc_m * max(0.0, min(1.0, ratio)), 2)
                ded_m = round(alloc_m - award_m, 2)

                if ded_m <= 0.0:
                    reason = f"{cat_name} is accurate and complete."
                elif award_m > 0.0:
                    reason = f"{cat_name} is partially correct ({round(ratio*100, 1)}% match)."
                else:
                    reason = f"{cat_name} was unsatisfactory or missing."

                deductions.append(
                    CriterionDeduction(
                        criterion=cat_name,
                        allocated_marks=alloc_m,
                        awarded_marks=award_m,
                        deducted_marks=ded_m,
                        reason=reason,
                        evidence=None,
                    )
                )

        logger.info(f"Aggregated Final Mark: {final_marks}/{max_marks} ({percentage}%) with {len(deductions)} criterion deductions.")

        return ScoreBreakdown(
            concept_score=round(c_score_10, 2),
            correctness_score=round(corr_score_10, 2),
            completeness_score=round(comp_score_10, 2),
            keyword_score=round(kw_score_10, 2),
            semantic_score=round(sem_score_10, 2),
            final_marks=final_marks,
            max_marks=max_marks,
            percentage=percentage,
            weights_used=weights_dict,
            criterion_deductions=deductions,
        )

