"""Evaluation API router executing full evaluation pipeline."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.services.ocr_refinement.refinement_engine import OCRRefinementEngine
from app.services.question_segmentation.question_segmenter import QuestionSegmenter
from app.services.rag.rag_engine import RAGEngine
from app.services.ideal_answer.ideal_answer_generator import IdealAnswerGenerator
from app.services.grading import EvaluatorOrchestrator, GradingResult

router = APIRouter(prefix="/evaluations", tags=["AI Grading Pipeline"])


class EvaluationRequest(BaseModel):
    exam_id: int
    question_number: str
    question_text: str
    raw_student_ocr_text: str
    answer_key_text: Optional[str] = "Standard KTU Model Answer"
    rubric_text: Optional[str] = "Definition: 2 marks, Advantages: 3 marks, Applications: 5 marks"
    max_marks: float = 10.0
    ocr_confidence: float = 0.88


@router.post("/evaluate", response_model=GradingResult)
async def run_evaluation_pipeline(request: EvaluationRequest):
    """Run full evaluation pipeline: OCR Refinement -> RAG -> Ideal Answer -> Research AI Grading Engine."""
    # 1. OCR Refinement
    refinement_engine = OCRRefinementEngine()
    refined = await refinement_engine.refine(request.raw_student_ocr_text)

    # 2. RAG Context Retrieval
    rag_engine = RAGEngine()
    rag_ctx = rag_engine.retrieve_context(
        exam_id=request.exam_id,
        question_number=request.question_number,
        question_text=request.question_text,
        answer_key_text=request.answer_key_text or "",
        rubric_text=request.rubric_text or "",
    )

    # 3. Ideal Answer Generation
    ideal_generator = IdealAnswerGenerator()
    ideal_result = await ideal_generator.generate_ideal_answer(
        question_number=request.question_number,
        question_text=request.question_text,
        rag_context=rag_ctx,
    )

    # 4. Refactored Evaluator Orchestrator
    orchestrator = EvaluatorOrchestrator()
    result = await orchestrator.evaluate(
        question_number=request.question_number,
        question_text=request.question_text,
        student_answer=refined.corrected_ocr,
        ideal_answer=ideal_result.ideal_answer,
        rubric_data=request.rubric_text,
        rag_context=rag_ctx,
        ocr_confidence=request.ocr_confidence,
        max_marks=request.max_marks,
    )

    return result
