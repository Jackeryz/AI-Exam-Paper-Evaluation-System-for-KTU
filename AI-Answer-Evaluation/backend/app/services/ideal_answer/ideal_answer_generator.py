"""Ideal Answer Generation service combining Question, Answer Key, Rubric, Study Material & RAG Context."""

from typing import Any, Optional
from pydantic import BaseModel

from app.services.llm.llm_interface import get_llm_provider, LLMProvider
from app.services.rag.rag_engine import RAGContext


class IdealAnswerResult(BaseModel):
    question_number: str
    ideal_answer: str
    key_concepts: list[str]


class IdealAnswerGenerator:
    """Synthesizes complete grading reference answer using multi-source context."""

    SYSTEM_PROMPT = (
        "You are a Senior KTU Engineering Professor synthesizing a comprehensive Model Ideal Answer.\n"
        "Integrate the Question, Official Answer Key, Rubric, and Study Notes into a complete reference answer.\n"
        "Identify key concepts and keywords required for full marks."
    )

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self.llm_provider = llm_provider or get_llm_provider()

    async def generate_ideal_answer(
        self,
        question_number: str,
        question_text: str,
        rag_context: RAGContext,
    ) -> IdealAnswerResult:
        notes_str = "\n---\n".join(rag_context.study_notes_context) if rag_context.study_notes_context else "None"
        
        prompt = (
            f"Question {question_number}: {question_text}\n\n"
            f"Official Answer Key: {rag_context.relevant_answer_key}\n\n"
            f"Scoring Rubric: {rag_context.relevant_rubric}\n\n"
            f"Retrieved Study Notes:\n{notes_str}\n\n"
            "Please generate the Ideal Master Reference Answer for evaluation."
        )

        response = await self.llm_provider.generate(prompt=prompt, system_prompt=self.SYSTEM_PROMPT)
        ideal_text = response.content.strip()

        return IdealAnswerResult(
            question_number=question_number,
            ideal_answer=ideal_text,
            key_concepts=["Core Definitions", "Legal/Economic Principles", "Structured Arguments", "KTU Terminology"],
        )
