from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.openapi import OPENAPI_DESCRIPTION, OPENAPI_TAGS, apply_openapi_metadata
from app.api.router import api_router
from app.core.config import settings
from app.schemas.common import ServiceInfoResponse

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=OPENAPI_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters={"displayRequestDuration": True},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Mount static files for serving uploaded images and exports
storage_dir = Path(settings.storage_base_dir)
storage_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(storage_dir)), name="static")


@app.get("/", response_model=ServiceInfoResponse, tags=["system"])
def read_root():
    return ServiceInfoResponse(
        name=settings.app_name,
        status="ready",
        version=settings.app_version,
        docs_url=app.docs_url or "",
        redoc_url=app.redoc_url or "",
        openapi_url=app.openapi_url or "",
    )


apply_openapi_metadata(app)
