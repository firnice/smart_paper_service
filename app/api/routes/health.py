from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.common import HealthCheckResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthCheckResponse)
def health_check():
    return HealthCheckResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
