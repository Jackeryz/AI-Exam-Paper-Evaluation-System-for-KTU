"""Answer Sheets API router for batch upload, local PP-OCRv6 extraction, and segmentation."""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from datetime import datetime
from app.database.session import get_db
from app.models.exam import Exam, Question
from app.models.evaluation import AnswerSheet, OCRResult, ExtractedAnswer
from app.models.user import User, UserRole
from app.core.security import get_current_user
from app.schemas.evaluation import (
    AnswerSheetResponse,
    ExtractedAnswerResponse,
    OCRCorrectionRequest,
    OCRApprovalRequest,
)
from app.services.ocr import get_ocr_service
from app.services.ocr_refinement.refinement_engine import OCRRefinementEngine
from app.services.question_segmentation.question_segmenter import QuestionSegmenter

router = APIRouter(prefix="/answer-sheets", tags=["Answer Sheets & OCR"])

UPLOAD_SHEETS_DIR = Path("./dataset/answer_sheets")
UPLOAD_SHEETS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


@router.post("/upload", response_model=List[AnswerSheetResponse], status_code=status.HTTP_201_CREATED)
@router.post("/upload/{exam_id_path}", response_model=List[AnswerSheetResponse], status_code=status.HTTP_201_CREATED)
async def upload_answer_sheets(
    files: List[UploadFile] = File(...),
    exam_id_path: Optional[int] = None,
    exam_id: Optional[int] = Form(None),
    exam_code: Optional[str] = Form(None),
    student_identifiers: Optional[str] = Form(None),
    student_identifier: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch upload student answer sheets associated with an examination code or ID."""
    # Resolve Exam
    actual_exam_id = exam_id_path or exam_id
    if actual_exam_id:
        exam_res = await db.execute(select(Exam).where(Exam.id == actual_exam_id))
        exam = exam_res.scalars().first()
    elif exam_code:
        exam_res = await db.execute(select(Exam).where(Exam.exam_code == exam_code.strip()))
        exam = exam_res.scalars().first()
    else:
        raise HTTPException(status_code=400, detail="Either exam_id or exam_code must be provided.")

    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found.")

    if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to upload answer sheets for this exam")

    exam_storage_dir = UPLOAD_SHEETS_DIR / f"exam_{exam.id}"
    exam_storage_dir.mkdir(parents=True, exist_ok=True)

    # Parse optional student identifiers
    id_source = student_identifier or student_identifiers
    id_list = [i.strip() for i in id_source.split(",")] if id_source else []

    created_sheets: List[AnswerSheet] = []

    for idx, upload_file in enumerate(files):
        ext = Path(upload_file.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue  # Skip unsupported

        # Assign student identifier (from list or derive from filename)
        identifier = id_list[idx] if idx < len(id_list) else Path(upload_file.filename).stem

        # Save file to disk
        dest_filename = f"{identifier}_{upload_file.filename}"
        dest_path = exam_storage_dir / dest_filename
        content = await upload_file.read()
        dest_path.write_bytes(content)

        new_sheet = AnswerSheet(
            exam_id=exam.id,
            student_identifier=identifier,
            original_filename=upload_file.filename,
            file_path=str(dest_path),
            status="UPLOADED",
        )
        db.add(new_sheet)
        created_sheets.append(new_sheet)

    await db.commit()

    output = []
    for s in created_sheets:
        await db.refresh(s)
        output.append(
            AnswerSheetResponse(
                id=s.id,
                exam_id=s.exam_id,
                student_identifier=s.student_identifier,
                original_filename=s.original_filename,
                file_path=s.file_path,
                page_count=s.page_count,
                status=s.status,
                uploaded_at=s.uploaded_at,
            )
        )
    return output


@router.get("", response_model=List[AnswerSheetResponse])
@router.get("/exam/{exam_id}", response_model=List[AnswerSheetResponse])
async def list_answer_sheets(
    exam_id: Optional[int] = None,
    exam_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List answer sheets for an examination."""
    stmt = (
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.extracted_answers),
        )
        .order_by(AnswerSheet.uploaded_at.desc())
    )

    if exam_id:
        stmt = stmt.where(AnswerSheet.exam_id == exam_id)
    elif exam_code:
        exam_res = await db.execute(select(Exam).where(Exam.exam_code == exam_code.strip()))
        exam = exam_res.scalars().first()
        if not exam:
            return []
        stmt = stmt.where(AnswerSheet.exam_id == exam.id)

    res = await db.execute(stmt)
    sheets = res.scalars().all()

def _to_answer_sheet_response(s: AnswerSheet) -> AnswerSheetResponse:
    """Helper to convert AnswerSheet model into unified AnswerSheetResponse schema."""
    ocr = s.ocr_result
    raw_text = ocr.raw_text if ocr else None
    refined_text = ocr.refined_text if ocr else None
    corrected_text = ocr.corrected_text if ocr else None
    confidence = ocr.confidence if ocr else None
    provider = ocr.refinement_provider if ocr else None
    model = ocr.refinement_model if ocr else None
    error_ref = ocr.refinement_error if ocr else None
    proposed = ocr.proposed_changes_json if (ocr and ocr.proposed_changes_json) else []
    uncertain = ocr.uncertain_spans_json if (ocr and ocr.uncertain_spans_json) else []
    approved = bool(ocr.is_teacher_approved) if (ocr and ocr.is_teacher_approved is not None) else False

    # Standardize refinement status contract
    if s.status in ("PROCESSING_OCR", "PROCESSING"):
        status_ref = "PROCESSING"
    elif not ocr or not raw_text:
        status_ref = "PENDING"
    elif approved:
        if ocr.refinement_status in ("TEACHER_APPROVED", "TEACHER_REVERTED_RAW"):
            status_ref = ocr.refinement_status
        else:
            status_ref = "TEACHER_APPROVED"
    elif ocr.refinement_status in ("FAILED", "FAILED_FALLBACK_RAW"):
        status_ref = "FAILED_FALLBACK_RAW"
    elif ocr.refinement_status == "SKIPPED":
        status_ref = "SKIPPED"
    elif ocr.refinement_status == "REFINED":
        status_ref = "REFINED"
    else:
        status_ref = ocr.refinement_status or "PENDING"

    # Explicit telemetry: if no LLM ran (PENDING or SKIPPED), provider and model are null
    if status_ref in ("PENDING", "SKIPPED"):
        provider = None
        model = None

    return AnswerSheetResponse(
        id=s.id,
        exam_id=s.exam_id,
        student_id=s.student_id,
        student_identifier=s.student_identifier,
        original_filename=s.original_filename,
        file_path=s.file_path or "",
        page_count=s.page_count or 1,
        status=s.status or "UPLOADED",
        error_message=s.error_message,
        raw_ocr_text=raw_text,
        refined_ocr_text=refined_text,
        corrected_text=corrected_text,
        ocr_confidence=confidence,
        refinement_provider=provider,
        refinement_model=model,
        refinement_status=status_ref,
        refinement_error=error_ref,
        proposed_changes=proposed,
        uncertain_spans=uncertain,
        is_teacher_approved=approved,
        uploaded_at=s.uploaded_at or datetime.utcnow(),
        extracted_answers=[
            ExtractedAnswerResponse(
                id=ea.id,
                answer_sheet_id=ea.answer_sheet_id,
                question_id=ea.question_id,
                question_number=ea.question_number,
                raw_ocr_text=ea.raw_ocr_text,
                refined_text=ea.refined_text,
                corrected_text=ea.corrected_text,
                is_manually_corrected=ea.is_manually_corrected,
                uncertain_spans=ea.uncertain_spans_json or [],
                page_number=ea.page_number,
            )
            for ea in (s.extracted_answers or [])
        ],
    )


async def _sync_extracted_answers(
    sheet: AnswerSheet,
    segmentation_text: str,
    raw_text: str,
    uncertain_spans: List[dict],
    is_approved: bool,
    db: AsyncSession,
) -> None:
    """Segment target text into Question answers while preserving raw OCR alignment."""
    # Segment both text versions for accurate segment alignment
    segmenter = QuestionSegmenter()
    segments = segmenter.segment_text(segmentation_text)

    raw_segments_map = {}
    if raw_text and raw_text != segmentation_text:
        raw_segments = segmenter.segment_text(raw_text)
        for rseg in raw_segments:
            r_content = getattr(rseg, "extracted_text", None) or getattr(rseg, "text", "")
            raw_segments_map[rseg.question_number.lower()] = r_content

    exam_questions = {q.question_number.lower(): q for q in sheet.exam.questions} if sheet.exam else {}

    # Clear existing extracted answers safely
    for ea in list(sheet.extracted_answers):
        await db.delete(ea)
    await db.flush()

    if segments:
        for seg in segments:
            matched_q = exam_questions.get(seg.question_number.lower())
            seg_content = getattr(seg, "extracted_text", None) or getattr(seg, "text", "")
            raw_seg_content = raw_segments_map.get(seg.question_number.lower(), seg_content)

            seg_uncertain = [
                u for u in uncertain_spans
                if u.get("fragment") and (u.get("fragment") in seg_content or u.get("fragment") in raw_seg_content)
            ]

            ea = ExtractedAnswer(
                answer_sheet_id=sheet.id,
                question_id=matched_q.id if matched_q else None,
                question_number=seg.question_number,
                raw_ocr_text=raw_seg_content,
                refined_text=seg_content,
                corrected_text=seg_content if is_approved else None,
                is_manually_corrected=is_approved,
                uncertain_spans_json=seg_uncertain,
                page_number=1,
            )
            db.add(ea)
    else:
        # Fallback: single answer block
        first_q = sheet.exam.questions[0] if sheet.exam and sheet.exam.questions else None
        ea = ExtractedAnswer(
            answer_sheet_id=sheet.id,
            question_id=first_q.id if first_q else None,
            question_number=first_q.question_number if first_q else "1(a)",
            raw_ocr_text=raw_text,
            refined_text=segmentation_text,
            corrected_text=segmentation_text if is_approved else None,
            is_manually_corrected=is_approved,
            uncertain_spans_json=uncertain_spans,
            page_number=1,
        )
        db.add(ea)


@router.get("", response_model=List[AnswerSheetResponse])
@router.get("/exam/{exam_id}", response_model=List[AnswerSheetResponse])
async def list_answer_sheets(
    exam_id: Optional[int] = None,
    exam_code: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List answer sheets for an examination."""
    stmt = (
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.exam),
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.extracted_answers),
        )
        .order_by(AnswerSheet.uploaded_at.desc())
    )

    if exam_id:
        exam_res = await db.execute(select(Exam).where(Exam.id == exam_id))
        exam = exam_res.scalars().first()
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found.")
        if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access answer sheets for this exam")
        stmt = stmt.where(AnswerSheet.exam_id == exam_id)
    elif exam_code:
        exam_res = await db.execute(select(Exam).where(Exam.exam_code == exam_code.strip()))
        exam = exam_res.scalars().first()
        if not exam:
            return []
        if current_user.role != UserRole.ADMIN and exam.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access answer sheets for this exam")
        stmt = stmt.where(AnswerSheet.exam_id == exam.id)
    else:
        if current_user.role != UserRole.ADMIN:
            stmt = stmt.join(Exam, AnswerSheet.exam_id == Exam.id).where(Exam.teacher_id == current_user.id)

    res = await db.execute(stmt)
    sheets = res.scalars().all()
    return [_to_answer_sheet_response(s) for s in sheets]


@router.get("/{sheet_id}", response_model=AnswerSheetResponse)
async def get_answer_sheet(
    sheet_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details for a single answer sheet."""
    res = await db.execute(
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.exam),
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.extracted_answers),
        )
        .where(AnswerSheet.id == sheet_id)
    )
    s = res.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="Answer sheet not found.")

    if current_user.role != UserRole.ADMIN and s.exam and s.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this answer sheet")

    return _to_answer_sheet_response(s)


@router.post("/{sheet_id}/process-ocr", response_model=AnswerSheetResponse)
async def process_sheet_ocr(
    sheet_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract handwritten text with PP-OCRv6 and execute LLM-assisted refinement."""
    res = await db.execute(
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.exam).selectinload(Exam.questions),
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.extracted_answers),
        )
        .where(AnswerSheet.id == sheet_id)
    )
    sheet = res.scalars().first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found.")

    if current_user.role != UserRole.ADMIN and sheet.exam and sheet.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to process this answer sheet")

    sheet.status = "PROCESSING_OCR"
    await db.commit()

    file_path = Path(sheet.file_path)
    if not file_path.exists():
        sheet.status = "FAILED"
        sheet.error_message = f"File not found on disk: {sheet.file_path}"
        await db.commit()
        raise HTTPException(status_code=400, detail="Sheet file does not exist on disk.")

    try:
        ocr_service = get_ocr_service("PADDLE")
        # Run local PP-OCRv6 across all pages
        if hasattr(ocr_service, "process_all_pages"):
            ocr_out = ocr_service.process_all_pages(file_path)
        else:
            single = ocr_service.process_file(file_path)
            ocr_out = {
                "text": single.text,
                "confidence": single.confidence,
                "page_count": 1,
                "bounding_boxes": [b.dict() for b in single.bounding_boxes],
                "engine": "PP-OCRv6",
            }

        sheet.page_count = ocr_out.get("page_count", 1)
        raw_extracted_text = ocr_out["text"]

        # Run LLM-assisted OCR refinement
        refinement_engine = OCRRefinementEngine()
        ref_res = await refinement_engine.refine(raw_extracted_text)

        # Check if already teacher-approved
        previously_approved = sheet.ocr_result.is_teacher_approved if sheet.ocr_result else False
        existing_corrected = sheet.ocr_result.corrected_text if sheet.ocr_result else None

        # Determine refinement success vs fallback
        is_refined = (ref_res.status == "REFINED")

        # Save or update OCRResult
        if sheet.ocr_result:
            sheet.ocr_result.raw_text = raw_extracted_text
            sheet.ocr_result.confidence = ocr_out["confidence"]
            sheet.ocr_result.engine_used = ocr_out.get("engine", "PP-OCRv6")
            sheet.ocr_result.bounding_boxes_json = ocr_out.get("bounding_boxes", [])
            sheet.ocr_result.refined_text = ref_res.refined_ocr_text if is_refined else None
            sheet.ocr_result.refinement_provider = ref_res.provider if ref_res.status != "SKIPPED" else None
            sheet.ocr_result.refinement_model = ref_res.model if ref_res.status != "SKIPPED" else None
            sheet.ocr_result.refinement_error = ref_res.error_message
            sheet.ocr_result.refinement_timestamp = ref_res.timestamp
            sheet.ocr_result.proposed_changes_json = [p.dict() for p in ref_res.proposed_changes]
            sheet.ocr_result.uncertain_spans_json = [u.dict() for u in ref_res.uncertain_spans]

            # Preserve teacher's manual correction if already reviewed
            if not previously_approved:
                sheet.ocr_result.refinement_status = ref_res.status
                sheet.ocr_result.corrected_text = ref_res.refined_ocr_text if is_refined else raw_extracted_text
            else:
                sheet.ocr_result.is_teacher_approved = True
                if sheet.ocr_result.refinement_status not in ("TEACHER_APPROVED", "TEACHER_REVERTED_RAW"):
                    sheet.ocr_result.refinement_status = "TEACHER_APPROVED"
        else:
            ocr_record = OCRResult(
                answer_sheet_id=sheet.id,
                raw_text=raw_extracted_text,
                refined_text=ref_res.refined_ocr_text if is_refined else None,
                corrected_text=ref_res.refined_ocr_text if is_refined else raw_extracted_text,
                confidence=ocr_out["confidence"],
                engine_used=ocr_out.get("engine", "PP-OCRv6"),
                bounding_boxes_json=ocr_out.get("bounding_boxes", []),
                refinement_provider=ref_res.provider if ref_res.status != "SKIPPED" else None,
                refinement_model=ref_res.model if ref_res.status != "SKIPPED" else None,
                refinement_status=ref_res.status,
                refinement_error=ref_res.error_message,
                refinement_timestamp=ref_res.timestamp,
                proposed_changes_json=[p.dict() for p in ref_res.proposed_changes],
                uncertain_spans_json=[u.dict() for u in ref_res.uncertain_spans],
                is_teacher_approved=False,
            )
            sheet.ocr_result = ocr_record
            db.add(ocr_record)

        await db.flush()

        # Determine which text version to use for Question Segmentation
        if previously_approved and existing_corrected:
            segmentation_text = existing_corrected
            is_approved = True
        elif ref_res.status == "REFINED" and ref_res.refined_ocr_text:
            segmentation_text = ref_res.refined_ocr_text
            is_approved = False
        else:
            segmentation_text = raw_extracted_text
            is_approved = False

        uncertain_spans_list = [u.dict() for u in ref_res.uncertain_spans]

        # Sync Extracted Answers
        await _sync_extracted_answers(
            sheet=sheet,
            segmentation_text=segmentation_text,
            raw_text=raw_extracted_text,
            uncertain_spans=uncertain_spans_list,
            is_approved=is_approved,
            db=db,
        )

        sheet.status = "OCR_COMPLETED"
        sheet.error_message = None
        await db.commit()
        db.expire(sheet)

    except Exception as exc:
        sheet.status = "FAILED"
        sheet.error_message = f"OCR Error: {str(exc)}"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to process OCR: {exc}") from exc

    # Refresh and return
    return await get_answer_sheet(sheet_id=sheet_id, current_user=current_user, db=db)


@router.post("/{sheet_id}/refine-ocr", response_model=AnswerSheetResponse)
async def refine_sheet_ocr(
    sheet_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run or retry LLM-assisted OCR refinement on existing raw OCR text."""
    res = await db.execute(
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.exam).selectinload(Exam.questions),
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.extracted_answers),
        )
        .where(AnswerSheet.id == sheet_id)
    )
    sheet = res.scalars().first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found.")

    if current_user.role != UserRole.ADMIN and sheet.exam and sheet.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to refine this answer sheet")

    if not sheet.ocr_result or not sheet.ocr_result.raw_text:
        raise HTTPException(
            status_code=400,
            detail="Answer sheet does not have raw OCR text. Run OCR extraction first."
        )

    raw_extracted_text = sheet.ocr_result.raw_text
    refinement_engine = OCRRefinementEngine()
    ref_res = await refinement_engine.refine(raw_extracted_text)

    previously_approved = sheet.ocr_result.is_teacher_approved
    existing_corrected = sheet.ocr_result.corrected_text
    existing_status = sheet.ocr_result.refinement_status

    is_refined = (ref_res.status == "REFINED")
    sheet.ocr_result.refined_text = ref_res.refined_ocr_text if is_refined else None
    sheet.ocr_result.refinement_provider = ref_res.provider if ref_res.status != "SKIPPED" else None
    sheet.ocr_result.refinement_model = ref_res.model if ref_res.status != "SKIPPED" else None
    sheet.ocr_result.refinement_error = ref_res.error_message
    sheet.ocr_result.refinement_timestamp = ref_res.timestamp
    sheet.ocr_result.proposed_changes_json = [p.dict() for p in ref_res.proposed_changes]
    sheet.ocr_result.uncertain_spans_json = [u.dict() for u in ref_res.uncertain_spans]

    if previously_approved:
        # Retry cannot overwrite newer teacher-approved text or reset approval
        sheet.ocr_result.is_teacher_approved = True
        sheet.ocr_result.corrected_text = existing_corrected
        sheet.ocr_result.refinement_status = existing_status or "TEACHER_APPROVED"
        seg_text = existing_corrected or raw_extracted_text
        is_app = True
    else:
        sheet.ocr_result.refinement_status = ref_res.status
        if is_refined and ref_res.refined_ocr_text:
            sheet.ocr_result.corrected_text = ref_res.refined_ocr_text
            seg_text = ref_res.refined_ocr_text
        else:
            sheet.ocr_result.corrected_text = raw_extracted_text
            seg_text = raw_extracted_text
        is_app = False

    uncertain_spans_list = [u.dict() for u in ref_res.uncertain_spans]
    await _sync_extracted_answers(
        sheet=sheet,
        segmentation_text=seg_text,
        raw_text=raw_extracted_text,
        uncertain_spans=uncertain_spans_list,
        is_approved=is_app,
        db=db,
    )

    await db.commit()
    db.expire(sheet)
    return await get_answer_sheet(sheet_id=sheet_id, current_user=current_user, db=db)


@router.put("/{sheet_id}/ocr-correction", response_model=AnswerSheetResponse)
async def update_ocr_correction(
    sheet_id: int,
    request: OCRCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save manual teacher corrections to OCR text and re-segment."""
    res = await db.execute(
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.exam).selectinload(Exam.questions),
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.extracted_answers),
        )
        .where(AnswerSheet.id == sheet_id)
    )
    sheet = res.scalars().first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found.")

    if current_user.role != UserRole.ADMIN and sheet.exam and sheet.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this answer sheet")

    new_text = request.corrected_text or request.refined_text
    if not new_text and request.action != "REVERT_TO_RAW":
        raise HTTPException(status_code=400, detail="corrected_text or refined_text must be provided.")

    if request.extracted_answer_id:
        ea_res = await db.execute(
            select(ExtractedAnswer).where(ExtractedAnswer.id == request.extracted_answer_id)
        )
        ea = ea_res.scalars().first()
        if ea:
            ea.corrected_text = new_text
            ea.refined_text = new_text
            ea.is_manually_corrected = True
    else:
        raw_text = sheet.ocr_result.raw_text if sheet.ocr_result else ""
        if request.action == "REVERT_TO_RAW":
            approved_text = raw_text
            status_tag = "TEACHER_REVERTED_RAW"
        else:
            approved_text = new_text
            status_tag = "TEACHER_APPROVED"

        if sheet.ocr_result:
            sheet.ocr_result.corrected_text = approved_text
            sheet.ocr_result.is_teacher_approved = True
            sheet.ocr_result.refinement_status = status_tag

        uncertain_spans = sheet.ocr_result.uncertain_spans_json if sheet.ocr_result else []

        await _sync_extracted_answers(
            sheet=sheet,
            segmentation_text=approved_text,
            raw_text=raw_text,
            uncertain_spans=uncertain_spans or [],
            is_approved=True,
            db=db,
        )

    await db.commit()
    db.expire(sheet)
    return await get_answer_sheet(sheet_id=sheet_id, current_user=current_user, db=db)


@router.post("/{sheet_id}/approve-refinement", response_model=AnswerSheetResponse)
async def approve_refinement(
    sheet_id: int,
    request: OCRApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Teacher action to accept LLM refinement, revert to raw OCR, or apply manual edits."""
    res = await db.execute(
        select(AnswerSheet)
        .options(
            selectinload(AnswerSheet.exam).selectinload(Exam.questions),
            selectinload(AnswerSheet.ocr_result),
            selectinload(AnswerSheet.extracted_answers),
        )
        .where(AnswerSheet.id == sheet_id)
    )
    sheet = res.scalars().first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found.")

    if current_user.role != UserRole.ADMIN and sheet.exam and sheet.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to approve this answer sheet")

    if not sheet.ocr_result:
        raise HTTPException(status_code=400, detail="No OCR result found for this answer sheet.")

    raw_text = sheet.ocr_result.raw_text
    refined_text = sheet.ocr_result.refined_text or raw_text

    if request.action == "ACCEPT_REFINEMENT":
        final_text = refined_text
        status_tag = "TEACHER_APPROVED"
    elif request.action == "REVERT_TO_RAW":
        final_text = raw_text
        status_tag = "TEACHER_REVERTED_RAW"
    elif request.action == "MANUAL_EDIT":
        if not request.edited_text:
            raise HTTPException(status_code=400, detail="edited_text must be provided for MANUAL_EDIT.")
        final_text = request.edited_text
        status_tag = "TEACHER_APPROVED"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown approval action: {request.action}")

    sheet.ocr_result.corrected_text = final_text
    sheet.ocr_result.is_teacher_approved = True
    sheet.ocr_result.refinement_status = status_tag

    uncertain_spans = sheet.ocr_result.uncertain_spans_json or []

    await _sync_extracted_answers(
        sheet=sheet,
        segmentation_text=final_text,
        raw_text=raw_text,
        uncertain_spans=uncertain_spans,
        is_approved=True,
        db=db,
    )

    await db.commit()
    db.expire(sheet)
    return await get_answer_sheet(sheet_id=sheet_id, current_user=current_user, db=db)


@router.get("/{sheet_id}/file")
async def get_answer_sheet_file(
    sheet_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve the original uploaded answer sheet document (PDF, PNG, JPG) for preview."""
    res = await db.execute(
        select(AnswerSheet)
        .options(selectinload(AnswerSheet.exam))
        .where(AnswerSheet.id == sheet_id)
    )
    sheet = res.scalars().first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found.")

    if current_user.role != UserRole.ADMIN and sheet.exam and sheet.exam.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

    file_path = Path(sheet.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found on disk.")

    ext = file_path.suffix.lower()
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"
    elif ext == ".tiff":
        media_type = "image/tiff"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=sheet.original_filename or file_path.name,
    )

