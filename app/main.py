import json
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.openapi import OPENAPI_DESCRIPTION, OPENAPI_TAGS, apply_openapi_metadata
from app.api.router import api_router
from app.core.config import settings
from app.core.logger import logger
from app.core.trace import REQUEST_ID_HEADER_NAME, TRACE_HEADER_NAME, reset_trace_id, resolve_trace_id, set_trace_id
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


async def _attach_trace_id_to_json_response(request: Request, response, trace_id: str):
    if not request.url.path.startswith("/api/"):
        return response
    if response.status_code in {204, 304}:
        return response

    content_type = str(response.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        return response

    if hasattr(response, "body_iterator"):
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
    else:
        body = bytes(response.body or b"")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )

    if not isinstance(payload, dict):
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )

    payload["trace_id"] = trace_id
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return JSONResponse(
        content=payload,
        status_code=response.status_code,
        headers=headers,
        background=response.background,
    )


@app.middleware("http")
async def attach_trace_id(request: Request, call_next):
    trace_id = resolve_trace_id(
        request.headers.get(TRACE_HEADER_NAME),
        request.headers.get(REQUEST_ID_HEADER_NAME),
    )
    request.state.trace_id = trace_id
    token = set_trace_id(trace_id)
    started_at = time.perf_counter()

    logger.info(
        "HTTP_IN request trace_id=%s method=%s path=%s query=%s client=%s",
        trace_id,
        request.method,
        request.url.path,
        request.url.query,
        request.client.host if request.client else None,
    )

    try:
        response = await call_next(request)
        response = await _attach_trace_id_to_json_response(request, response, trace_id)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        response.headers[TRACE_HEADER_NAME] = trace_id
        logger.info(
            "HTTP_IN response trace_id=%s method=%s path=%s status=%s elapsed_ms=%d",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
    except Exception:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "HTTP_IN error trace_id=%s method=%s path=%s elapsed_ms=%d",
            trace_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise
    finally:
        reset_trace_id(token)


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
