"""Comprehensive unit & integration tests for pipeline services and the refactored AI Grading System."""

import pytest
from app.services.question_segmentation.question_segmenter import QuestionSegmenter
from app.services.ocr_refinement.refinement_engine import OCRRefinementEngine
from app.services.grading import (
    GradingMetrics,
    RubricParser,
    KeywordExtractor,
    ScoreAggregator,
    ConfidenceCalculator,
    EvaluatorOrchestrator,
)
from app.services.grading_engine.evaluator import AIGradingEngine


def test_question_segmentation():
    segmenter = QuestionSegmenter()
    ocr_text = (
        "1(a) Explain the fundamental rights guaranteed under Article 19.\n"
        "Article 19 protects freedom of speech and expression.\n"
        "1(b) Describe the powers of the Supreme Court of India.\n"
        "The Supreme Court has original and appellate jurisdiction.\n"
    )
    segments = segmenter.segment_text(ocr_text)
    assert len(segments) == 2
    assert segments[0].question_number == "1(a)"
    assert segments[1].question_number == "1(b)"


@pytest.mark.anyio
async def test_ocr_refinement():
    refinement_engine = OCRRefinementEngine()
    raw_ocr = "Th3 c0nstitution of lndia is the supreme law."
    result = await refinement_engine.refine(raw_ocr)
    assert result.corrected_ocr is not None


def test_grading_metrics():
    # Cosine Similarity
    sim = GradingMetrics.cosine_similarity([1.0, 0.0], [1.0, 0.0])
    assert sim == 1.0

    # Keyword Coverage
    cov = GradingMetrics.keyword_coverage(
        "Article 14 guarantees equality before law",
        ["equality", "law", "article 14"],
    )
    assert cov == 1.0

    # Length Normalization
    norm = GradingMetrics.length_normalization("short text", "ideal long text explanation with many details and words")
    assert 0.0 <= norm <= 1.0


def test_rubric_parser():
    parser = RubricParser()
    parsed = parser.parse("Definition: 2 marks, Advantages: 3 marks, Applications: 5 marks")
    assert len(parsed.sections) == 3
    assert parsed.sections[0].name.lower() == "definition"
    assert parsed.sections[0].allocated_marks == 2.0


def test_keyword_extractor():
    extractor = KeywordExtractor()
    parser = RubricParser()
    parsed = parser.parse("Definition: 2 marks")
    kw_set = extractor.extract(
        question_text="What are Fundamental Rights?",
        ideal_answer="Fundamental Rights under Article 19 guarantee Freedom of Speech.",
        rubric=parsed,
        study_material=["Constitution of India Article 19"],
    )
    assert len(kw_set.required_keywords) > 0


def test_score_aggregator():
    aggregator = ScoreAggregator()
    parser = RubricParser()
    parsed = parser.parse("Definition: 2 marks, Advantages: 3 marks, Applications: 5 marks")
    
    breakdown = aggregator.aggregate(
        concept_score=8.0,
        correctness_score=8.0,
        completeness_score=8.0,
        keyword_coverage=0.8,
        semantic_similarity=0.8,
        parsed_rubric=parsed,
        max_marks=10.0,
    )
    assert breakdown.final_marks == 8.0
    assert breakdown.percentage == 80.0
    assert len(breakdown.criterion_deductions) == 3
    assert breakdown.criterion_deductions[0].criterion == "Definition"


@pytest.mark.anyio
async def test_feedback_generator():
    from app.services.grading.feedback_generator import FeedbackGenerator
    generator = FeedbackGenerator()
    aggregator = ScoreAggregator()
    parser = RubricParser()
    parsed = parser.parse("Definition: 2 marks, Advantages: 3 marks, Applications: 5 marks")
    breakdown = aggregator.aggregate(
        concept_score=6.0,
        correctness_score=6.0,
        completeness_score=6.0,
        keyword_coverage=0.6,
        semantic_similarity=0.6,
        parsed_rubric=parsed,
        max_marks=10.0,
    )

    feedback = await generator.generate_explainable_feedback(
        question_number="1(a)",
        question_text="Explain Constitution Principles",
        student_answer="Partial explanation",
        ideal_answer="Detailed explanation",
        score_breakdown=breakdown,
        parsed_rubric=parsed,
    )

    assert feedback.overall_summary is not None
    assert len(feedback.weaknesses) > 0


def test_confidence_calculator():
    calculator = ConfidenceCalculator(threshold=0.70)
    conf = calculator.calculate(
        ocr_confidence=0.90,
        semantic_similarity=0.85,
        keyword_coverage=0.80,
        rag_relevance=0.90,
        is_json_valid=True,
    )
    assert conf.overall_confidence > 0.70
    assert not conf.is_flagged


@pytest.mark.anyio
async def test_evaluator_orchestrator():
    orchestrator = EvaluatorOrchestrator()
    result = await orchestrator.evaluate(
        question_number="1(a)",
        question_text="Explain Article 14 of the Constitution of India.",
        student_answer="Article 14 guarantees equality before law and equal protection of laws to all persons in India.",
        ideal_answer="Article 14 provides equality before law and equal protection of laws under the Constitution.",
        rubric_data="Definition: 5 marks, Application: 5 marks",
        max_marks=10.0,
    )

    assert result.marks_awarded > 0.0
    assert result.confidence_score > 0.0
    assert result.score_breakdown.final_marks == result.marks_awarded
    assert result.research_metrics.cosine_similarity > 0.0


@pytest.mark.anyio
async def test_ai_grading_engine_backward_compatibility():
    grading_engine = AIGradingEngine()
    student_ans = "Article 14 provides equality before law and equal protection of laws to all citizens within India."
    ideal_ans = "Article 14 ensures equality before law and equal protection of laws under the Constitution of India."

    result = await grading_engine.evaluate_answer(
        question_number="1(a)",
        student_answer=student_ans,
        ideal_answer=ideal_ans,
        max_marks=10.0,
        keywords=["Equality", "Article 14", "Protection"],
    )

    assert result.marks_awarded > 0.0
    assert result.confidence_score > 0.0
