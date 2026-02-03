from fastapi import APIRouter

from app.schemas.variants import VariantsRequest, VariantsResponse
from app.services import variant_service

router = APIRouter()


@router.post("/api/variants/generate", response_model=VariantsResponse)
def generate_variants(payload: VariantsRequest):
    items = variant_service.generate_variants(payload.source_text, payload.count)
    return VariantsResponse(items=items)
