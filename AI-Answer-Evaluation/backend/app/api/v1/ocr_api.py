"""OCR API router invoking backend OCRInterface."""

from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Query, HTTPException, status

from app.services.ocr import get_ocr_service, OCRResultData

router = APIRouter(prefix="/ocr", tags=["OCR Ingestion"])


@router.post("/process", response_model=OCRResultData)
async def process_ocr(
    file: UploadFile = File(...),
    page_number: int = Query(default=1),
    engine: str = Query(default="PADDLE", description="PADDLE, TROCR, EASYOCR, GOOGLE_VISION, MISTRAL"),
):
    """Run OCR on uploaded file using configured or requested OCR engine."""
    temp_dir = Path("./dataset/ocr_output/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        ocr_service = get_ocr_service(engine_override=engine)
        result = ocr_service.process_file(temp_path, page_number=page_number)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR Processing error: {str(exc)}") from exc
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
