import logging

from fastapi import APIRouter, HTTPException

from app.schemas.variants import VariantsRequest, VariantsResponse
from app.services import variant_service

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


@router.post("/api/variants/generate", response_model=VariantsResponse)
def generate_variants(payload: VariantsRequest):
    try:
        items = variant_service.generate_variants(
            payload.source_text,
            payload.count,
            grade=payload.grade,
            subject=payload.subject,
        )
    except RuntimeError as exc:
        logger.exception("Variants generation failed")
        raise HTTPException(status_code=502, detail="LLM service unavailable.") from exc
    return VariantsResponse(items=items)
