"""Pipeline Orchestrator for AI Answer Evaluation integrating Score Aggregation and Explainable Feedback Generation."""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import logger
from app.services.llm.llm_interface import get_llm_provider, LLMProvider
from app.services.embedding.embedding_interface import get_embedding_provider, EmbeddingProvider
from app.services.rag.rag_engine import RAGContext

from app.services.grading.grading_metrics import GradingMetrics
from app.services.grading.rubric_parser import RubricParser, ParsedRubric
from app.services.grading.keyword_extractor import KeywordExtractor, ExtractedKeywordSet
from app.services.grading.score_aggregator import ScoreAggregator, ScoreBreakdown, CriterionDeduction
from app.services.grading.confidence_calculator import ConfidenceCalculator, ConfidenceBreakdown
from app.services.grading.feedback_generator import FeedbackGenerator, StructuredFeedback


class QualitativeLLMEvaluation(BaseModel):
    """LLM Qualitative Analysis Output Schema (NO MARKS, NO CONFIDENCE)."""
    concept_understanding: float = Field(default=7.0, description="0.0 to 10.0 qualitative score")
    correctness: float = Field(default=7.0, description="0.0 to 10.0 qualitative score")
    completeness: float = Field(default=7.0, description="0.0 to 10.0 qualitative score")
    missing_concepts: List[str] = Field(default_factory=list)
    feedback: str = Field(default="Sufficient understanding of core concepts.")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    improvement_suggestions: str = Field(default="Include more technical detail for full marks.")
    reasoning: str = Field(default="Qualitative evaluation based on rubric and ideal answer.")


class ResearchGradingMetrics(BaseModel):
    """Exposes all metric scores for statistical research and benchmarking."""
    cosine_similarity: float
    keyword_coverage_ratio: float
    concept_overlap_ratio: float
    length_normalization_ratio: float
    section_coverage_ratio: float


class GradingResult(BaseModel):
    """Complete, research-grade Grading Result with Explainable Feedback and Criterion Deductions."""
    question_number: str
    marks_awarded: float
    max_marks: float
    percentage: float
    confidence_score: float
    is_flagged: bool
    feedback: str
    improvement_suggestions: str
    reasons_for_grading: str
    
    # Explainable Feedback & Rubric Deductions
    criterion_deductions: List[CriterionDeduction] = Field(default_factory=list)
    structured_feedback: StructuredFeedback
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    reasons_for_deduction: List[str] = Field(default_factory=list)
    overall_summary: str = ""

    # Detailed Research & Evaluation Breakdowns
    score_breakdown: ScoreBreakdown
    confidence_breakdown: ConfidenceBreakdown
    qualitative_evaluation: QualitativeLLMEvaluation
    research_metrics: ResearchGradingMetrics
    extracted_keywords: ExtractedKeywordSet


class EvaluatorOrchestrator:
    """Orchestrates the evaluation pipeline without embedding formulas or self-confidence."""

    PROMPT_TEMPLATE = (
        "You are an expert AI Examiner evaluating a handwritten student answer paper for a KTU Engineering Examination.\n"
        "Analyze the student's answer strictly against the Ideal Answer, Rubric, and Study Notes.\n\n"
        "IMPORTANT INSTRUCTIONS:\n"
        "- Do NOT assign final numerical marks.\n"
        "- Do NOT assign confidence scores.\n"
        "- Provide qualitative scores (0.0 to 10.0) for Concept Understanding, Correctness, and Completeness.\n"
        "- Identify missing concepts, strengths, weaknesses, and improvement suggestions.\n\n"
        "Input Data:\n"
        "Question {question_number}: {question_text}\n\n"
        "Ideal Master Answer:\n{ideal_answer}\n\n"
        "Student Answer (OCR Extracted & Refined):\n{student_answer}\n\n"
        "Rubric Guidelines:\n{rubric_rules}\n\n"
        "Retrieved Study Notes:\n{study_notes}\n\n"
        "Required Keywords to Check: {keywords}\n\n"
        "Return your qualitative analysis as a JSON object adhering to this schema:\n"
        "{{\n"
        '  "concept_understanding": float (0.0 to 10.0),\n'
        '  "correctness": float (0.0 to 10.0),\n'
        '  "completeness": float (0.0 to 10.0),\n'
        '  "missing_concepts": ["list", "of", "missing"],\n'
        '  "feedback": "string summary",\n'
        '  "strengths": ["list of strengths"],\n'
        '  "weaknesses": ["list of weaknesses"],\n'
        '  "improvement_suggestions": "string suggestions",\n'
        '  "reasoning": "detailed reasoning"\n'
        "}}"
    )

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.settings = get_settings()
        self.llm_provider = llm_provider or get_llm_provider()
        self.embedding_provider = embedding_provider or get_embedding_provider()

        self.rubric_parser = RubricParser()
        self.keyword_extractor = KeywordExtractor()
        self.score_aggregator = ScoreAggregator()
        self.confidence_calculator = ConfidenceCalculator()
        self.feedback_generator = FeedbackGenerator(llm_provider=self.llm_provider)

    async def evaluate(
        self,
        question_number: str,
        question_text: str,
        student_answer: str,
        ideal_answer: str,
        rubric_data: Any = None,
        rag_context: Optional[RAGContext] = None,
        ocr_confidence: float = 0.85,
        max_marks: float = 10.0,
    ) -> GradingResult:
        """Run the full deterministic pipeline."""
        # 1. Parse Rubric
        parsed_rubric = self.rubric_parser.parse(rubric_data, default_max_marks=max_marks)

        # 2. Extract Keywords & Concepts
        study_notes = rag_context.study_notes_context if rag_context else []
        keyword_set = self.keyword_extractor.extract(
            question_text=question_text,
            ideal_answer=ideal_answer,
            rubric=parsed_rubric,
            study_material=study_notes,
        )

        # 3. Compute Quantitative Metrics
        vec_student = self.embedding_provider.embed_query(student_answer)
        vec_ideal = self.embedding_provider.embed_query(ideal_answer)
        cos_sim = GradingMetrics.cosine_similarity(vec_student, vec_ideal)
        kw_cov = GradingMetrics.keyword_coverage(student_answer, keyword_set.required_keywords, keyword_set.synonyms)
        concept_cov = GradingMetrics.concept_overlap(student_answer, keyword_set.important_concepts)
        len_norm = GradingMetrics.length_normalization(student_answer, ideal_answer)
        sec_cov = GradingMetrics.section_coverage_ratio(
            student_answer, [s.name for s in parsed_rubric.sections]
        )

        research_metrics = ResearchGradingMetrics(
            cosine_similarity=round(cos_sim, 4),
            keyword_coverage_ratio=round(kw_cov, 4),
            concept_overlap_ratio=round(concept_cov, 4),
            length_normalization_ratio=round(len_norm, 4),
            section_coverage_ratio=round(sec_cov, 4),
        )

        # 4. Invoke LLM for Qualitative Analysis only
        prompt = self.PROMPT_TEMPLATE.format(
            question_number=question_number,
            question_text=question_text,
            ideal_answer=ideal_answer,
            student_answer=student_answer,
            rubric_rules=parsed_rubric.raw_rubric_text,
            study_notes="\n---\n".join(study_notes) if study_notes else "None",
            keywords=", ".join(keyword_set.required_keywords),
        )

        llm_response = await self.llm_provider.generate(prompt=prompt)
        is_json_valid = False
        qualitative_eval: QualitativeLLMEvaluation

        try:
            raw_content = llm_response.content
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()

            parsed_json = json.loads(raw_content)
            qualitative_eval = QualitativeLLMEvaluation(**parsed_json)
            is_json_valid = True
        except Exception as exc:
            logger.warning(f"LLM JSON parsing fallback triggered ({exc}). Computing deterministic rule-based qualitative evaluation.")
            c_score = float(round(concept_cov * 10.0, 2))
            corr_score = float(round(cos_sim * 10.0, 2))
            comp_score = float(round(len_norm * sec_cov * 10.0, 2))

            qualitative_eval = QualitativeLLMEvaluation(
                concept_understanding=c_score,
                correctness=corr_score,
                completeness=comp_score,
                missing_concepts=[c for c in keyword_set.important_concepts if c.lower() not in student_answer.lower()],
                feedback=f"Rule-based evaluation: Semantic match is {round(cos_sim*100, 1)}% with keyword coverage of {round(kw_cov*100, 1)}%.",
                strengths=["Automated metric match"],
                weaknesses=["Parsing required metric fallback"],
                improvement_suggestions="Ensure key terminology and full explanations are included.",
                reasoning="Computed via deterministic rule-based fallback based on semantic similarity and keyword metrics.",
            )

        # 5. Score Aggregation (LLM NEVER sets final marks directly)
        score_breakdown = self.score_aggregator.aggregate(
            concept_score=qualitative_eval.concept_understanding,
            correctness_score=qualitative_eval.correctness,
            completeness_score=qualitative_eval.completeness,
            keyword_coverage=kw_cov,
            semantic_similarity=cos_sim,
            parsed_rubric=parsed_rubric,
            max_marks=max_marks,
        )

        # 6. Confidence Calculation
        rag_relevance = 0.90 if study_notes else 0.75
        confidence_breakdown = self.confidence_calculator.calculate(
            ocr_confidence=ocr_confidence,
            semantic_similarity=cos_sim,
            keyword_coverage=kw_cov,
            rag_relevance=rag_relevance,
            is_json_valid=is_json_valid,
        )

        # 7. Explainable Feedback Generation (From pre-computed deductions)
        structured_fb = await self.feedback_generator.generate_explainable_feedback(
            question_number=question_number,
            question_text=question_text,
            student_answer=student_answer,
            ideal_answer=ideal_answer,
            score_breakdown=score_breakdown,
            parsed_rubric=parsed_rubric,
        )

        return GradingResult(
            question_number=question_number,
            marks_awarded=score_breakdown.final_marks,
            max_marks=max_marks,
            percentage=score_breakdown.percentage,
            confidence_score=confidence_breakdown.overall_confidence,
            is_flagged=confidence_breakdown.is_flagged,
            feedback=structured_fb.overall_summary or qualitative_eval.feedback,
            improvement_suggestions="; ".join(structured_fb.improvement_suggestions) if structured_fb.improvement_suggestions else qualitative_eval.improvement_suggestions,
            reasons_for_grading=qualitative_eval.reasoning,
            criterion_deductions=score_breakdown.criterion_deductions,
            structured_feedback=structured_fb,
            strengths=structured_fb.strengths,
            weaknesses=structured_fb.weaknesses,
            reasons_for_deduction=structured_fb.reasons_for_deduction,
            overall_summary=structured_fb.overall_summary,
            score_breakdown=score_breakdown,
            confidence_breakdown=confidence_breakdown,
            qualitative_evaluation=qualitative_eval,
            research_metrics=research_metrics,
            extracted_keywords=keyword_set,
        )
