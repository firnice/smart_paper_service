from fastapi import APIRouter, File, UploadFile

from app.schemas.ocr import OcrExtractResponse
from app.services import ocr_service

router = APIRouter()


@router.post("/api/ocr/extract", response_model=OcrExtractResponse)
async def extract_questions(file: UploadFile = File(...)):
    items = ocr_service.extract_questions(file.filename or "upload")
    return OcrExtractResponse(items=items)
