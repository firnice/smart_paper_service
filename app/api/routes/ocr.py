import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.ocr import OcrExtractResponse
from app.services import ocr_service

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


@router.post("/api/ocr/extract", response_model=OcrExtractResponse)
async def extract_questions(file: UploadFile = File(...)):
    content_type = file.content_type or "image/png"
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty upload.")
        logger.info(
            "OCR upload received filename=%s bytes=%d content_type=%s",
            file.filename or "upload",
            len(image_bytes),
            content_type,
        )
        items = ocr_service.extract_questions(image_bytes, content_type, file.filename or "upload")
    except RuntimeError as exc:
        logger.exception("OCR failed")
        raise HTTPException(status_code=502, detail="OCR service unavailable.") from exc
    return OcrExtractResponse(items=items)
