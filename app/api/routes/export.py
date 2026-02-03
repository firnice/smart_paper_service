from fastapi import APIRouter

from app.schemas.export import ExportRequest, ExportResponse
from app.services import export_service

router = APIRouter()


@router.post("/api/export", response_model=ExportResponse)
def create_export(payload: ExportRequest):
    return export_service.create_export(
        title=payload.title,
        original_text=payload.original_text,
        variants=payload.variants,
        include_images=payload.include_images,
    )
