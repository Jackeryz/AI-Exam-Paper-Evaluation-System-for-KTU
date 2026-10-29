"""Reference Answers API router for Multi-Model Ideal Answer proposals, consolidation, and teacher approval."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.exam import Exam, Question, ReferenceAnswerProposal, ApprovedReferenceAnswer, AnswerKey, Rubric
from app.models.user import User, UserRole
from app.core.security import get_current_user
from app.schemas.exam import ReferenceAnswerProposalResponse, ApprovedReferenceAnswerResponse
from app.services.llm.llm_interface import get_llm_provider, OllamaProvider
from app.core.config import get_settings

router = APIRouter(prefix="/reference-answers", tags=["Multi-Model Reference Answer Studio"])


class GenerateProposalsRequest(BaseModel):
    providers: Optional[List[str]] = None  # e.g. ["OLLAMA:qwen3", "OLLAMA:deepseek-r1:8b"] or None for default


class ApproveReferenceRequest(BaseModel):
    approved_answer: Optional[str] = None
    ideal_answer: Optional[str] = None
    approved_rubric_json: Optional[Dict[str, float]] = None
    rubric_criteria: Optional[List[Dict[str, Any]]] = None
    key_concepts: Optional[List[str]] = None
    required_concepts: Optional[List[str]] = None
    mandatory_keywords: Optional[List[str]] = None


@router.post("/question/{question_id}/generate-proposals", response_model=List[ReferenceAnswerProposalResponse])
async def generate_reference_proposals(
    question_id: int,
    request: Optional[GenerateProposalsRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query multiple configured LLM models to generate reference answer proposals and rubric allocations."""
    settings = get_settings()

    res = await db.execute(
        select(Question)
        .options(
            selectinload(Question.exam),
            selectinload(Question.answer_key),
            selectinload(Question.rubric),
            selectinload(Question.reference_proposals),
        )
        .where(Question.id == question_id)
    )
    question = res.scalars().first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    if current_user.role != UserRole.ADMIN and question.exam and question.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to generate proposals for this exam")

    # Determine model configurations to query
    models_to_query = [
        ("OLLAMA", settings.LLM_MODEL),
        ("OLLAMA", "deepseek-r1:8b"),
    ]

    official_solution = question.answer_key.ideal_solution if question.answer_key else "Not provided"
    existing_rubric = json.dumps(question.rubric.criteria_json) if question.rubric and question.rubric.criteria_json else "None"

    created_proposals: List[ReferenceAnswerProposal] = []

    for provider_name, model_name in models_to_query:
        provider = get_llm_provider(provider_name, model_override=model_name)

        system_prompt = (
            "You are a Senior Engineering University Professor synthesizing a reference model answer and rubric.\n"
            "Format your output strictly as JSON with keys:\n"
            "- 'ideal_answer': comprehensive reference answer\n"
            "- 'key_concepts': list of mandatory technical concepts\n"
            "- 'rubric': dictionary mapping criterion name to numerical mark allocation totaling the question's max marks.\n"
            f"Question Maximum Marks: {question.max_marks}"
        )

        prompt = (
            f"Question {question.question_number}: {question.text}\n"
            f"Maximum Marks: {question.max_marks}\n"
            f"Official Answer Key Reference: {official_solution}\n"
            f"Existing Marking Scheme: {existing_rubric}\n\n"
            "Generate the master model answer, key concepts, and structured rubric criteria."
        )

        try:
            llm_res = await provider.generate(prompt=prompt, system_prompt=system_prompt)
            raw_content = llm_res.content

            # Parse or structured fallback
            proposed_text = raw_content
            key_concepts = ["Core Definition", "Technical Principles", "KTU Terminology", "Practical Application"]
            rubric_dict = {
                "Definition & Principles": round(question.max_marks * 0.4, 1),
                "Explanation & Completeness": round(question.max_marks * 0.3, 1),
                "Applications & Case Study": round(question.max_marks * 0.3, 1),
            }

            # Attempt JSON parsing if LLM returned JSON
            try:
                # Find JSON block if present
                clean_json_str = raw_content.strip()
                if "```json" in clean_json_str:
                    clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json_str:
                    clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()

                parsed = json.loads(clean_json_str)
                if isinstance(parsed, dict):
                    proposed_text = parsed.get("ideal_answer", proposed_text)
                    if "key_concepts" in parsed and isinstance(parsed["key_concepts"], list):
                        key_concepts = parsed["key_concepts"]
                    if "rubric" in parsed and isinstance(parsed["rubric"], dict):
                        rubric_dict = {k: float(v) for k, v in parsed["rubric"].items()}
            except Exception:
                pass  # Use fallback structured values

            proposal = ReferenceAnswerProposal(
                question_id=question.id,
                provider=provider_name,
                model=model_name,
                proposed_answer=proposed_text,
                proposed_rubric_json=rubric_dict,
                key_concepts_json=key_concepts,
            )
            db.add(proposal)
            created_proposals.append(proposal)

        except Exception as exc:
            # Independent provider failure tolerance
            continue

    await db.commit()

    # Re-fetch all proposals for this question
    proposals_res = await db.execute(
        select(ReferenceAnswerProposal)
        .where(ReferenceAnswerProposal.question_id == question.id)
        .order_by(ReferenceAnswerProposal.created_at.desc())
    )
    return proposals_res.scalars().all()


@router.get("/question/{question_id}/proposals", response_model=List[ReferenceAnswerProposalResponse])
async def get_reference_proposals(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all generated reference answer proposals for a question."""
    q_res = await db.execute(
        select(Question).options(selectinload(Question.exam)).where(Question.id == question_id)
    )
    question = q_res.scalars().first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    if current_user.role != UserRole.ADMIN and question.exam and question.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access proposals for this exam")

    res = await db.execute(
        select(ReferenceAnswerProposal)
        .where(ReferenceAnswerProposal.question_id == question_id)
        .order_by(ReferenceAnswerProposal.created_at.desc())
    )
    return res.scalars().all()


@router.get("/question/{question_id}/approved", response_model=Optional[ApprovedReferenceAnswerResponse])
async def get_approved_reference(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the teacher-approved reference answer and rubric for a question."""
    q_res = await db.execute(
        select(Question).options(selectinload(Question.exam)).where(Question.id == question_id)
    )
    question = q_res.scalars().first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    if current_user.role != UserRole.ADMIN and question.exam and question.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access approved reference for this exam")

    res = await db.execute(
        select(ApprovedReferenceAnswer).where(ApprovedReferenceAnswer.question_id == question_id)
    )
    return res.scalars().first()


@router.post("/question/{question_id}/approve", response_model=ApprovedReferenceAnswerResponse)
async def approve_reference_answer(
    question_id: int,
    request: ApproveReferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Teacher review, edit, and approval of consolidated reference answer and rubric."""
    res = await db.execute(
        select(Question)
        .options(
            selectinload(Question.exam),
            selectinload(Question.rubric),
            selectinload(Question.answer_key),
            selectinload(Question.approved_reference),
        )
        .where(Question.id == question_id)
    )
    question = res.scalars().first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    if current_user.role != UserRole.ADMIN and question.exam and question.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to approve reference answers for this exam")

    answer_text = request.approved_answer or request.ideal_answer
    if not answer_text:
        raise HTTPException(status_code=400, detail="Approved ideal answer must be provided.")

    rubric_dict = request.approved_rubric_json
    if not rubric_dict and request.rubric_criteria:
        rubric_dict = {
            item.get("criterion", f"Crit_{i}"): float(item.get("allocated_marks", 0))
            for i, item in enumerate(request.rubric_criteria)
        }
    if not rubric_dict:
        rubric_dict = {"General Content & Understanding": float(question.max_marks)}

    concepts = request.key_concepts or request.required_concepts or request.mandatory_keywords or []

    # Validate that rubric allocations sum to the question's maximum marks
    total_rubric_marks = round(sum(rubric_dict.values()), 2)
    if abs(total_rubric_marks - question.max_marks) > 0.05:
        raise HTTPException(
            status_code=400,
            detail=f"Approved rubric sum ({total_rubric_marks}) must equal question maximum marks ({question.max_marks})."
        )

    # Update or create ApprovedReferenceAnswer
    if question.approved_reference:
        app_ref = question.approved_reference
        app_ref.approved_answer = answer_text
        app_ref.approved_rubric_json = rubric_dict
        app_ref.key_concepts_json = concepts
        app_ref.approved_by = current_user.id
        app_ref.version += 1
        app_ref.approved_at = datetime.utcnow()
    else:
        app_ref = ApprovedReferenceAnswer(
            question_id=question.id,
            approved_answer=answer_text,
            approved_rubric_json=rubric_dict,
            key_concepts_json=concepts,
            approved_by=current_user.id,
            version=1,
            approved_at=datetime.utcnow(),
        )
        db.add(app_ref)

    # Sync back to Rubric and AnswerKey for consistency
    if question.rubric:
        question.rubric.criteria_json = rubric_dict
    else:
        db.add(Rubric(question_id=question.id, criteria_json=rubric_dict))

    if question.answer_key:
        question.answer_key.model_answer = answer_text
        if concepts:
            question.answer_key.keywords = concepts
    else:
        db.add(AnswerKey(question_id=question.id, ideal_solution=answer_text, keywords=concepts))

    await db.commit()
    await db.refresh(app_ref)
    return app_ref
