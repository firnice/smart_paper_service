from uuid import uuid4

from app.schemas.export import ExportResponse


def create_export(
    title: str,
    original_text: str,
    variants: list[str],
    include_images: bool,
) -> ExportResponse:
    """Stub export job creation."""
    return ExportResponse(
        job_id=str(uuid4()),
        status="queued",
        download_url=None,
    )
