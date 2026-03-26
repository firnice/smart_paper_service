import base64
from typing import Any, Optional

from app.core.config import settings
from app.core.logger import logger
from app.services.http_client import HttpClientError, post_json


def is_annotation_clean_fallback_enabled() -> bool:
    return bool(settings.enable_annotation_saas_fallback and settings.annotation_clean_api_url)


def _extract_clean_image_base64(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("clean_image_base64", "image_base64", "result_base64"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = payload.get("result")
        if isinstance(nested, dict):
            return _extract_clean_image_base64(nested)
    return None


def clean_diagram_with_saas(
    image_bytes: bytes,
    *,
    content_type: str = "image/png",
    file_name: str = "diagram.png",
) -> Optional[bytes]:
    if not is_annotation_clean_fallback_enabled():
        return None

    body = {
        "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
        "content_type": content_type,
        "file_name": file_name,
    }

    extra_headers = {}
    if settings.annotation_clean_api_key:
        extra_headers["Authorization"] = f"Bearer {settings.annotation_clean_api_key}"

    timeout_seconds = max(3, int(settings.annotation_clean_timeout_seconds))
    try:
        payload = post_json(
            settings.annotation_clean_api_url,
            body,
            trace_id=f"annotation_clean:{file_name}",
            headers=extra_headers or None,
            timeout_seconds=timeout_seconds,
        )
        encoded = _extract_clean_image_base64(payload)
        if not encoded:
            logger.warning("Annotation clean SaaS response missing clean image field")
            return None
        return base64.b64decode(encoded)
    except HttpClientError as exc:
        logger.warning("Annotation clean SaaS request failed: %s", str(exc))
        return None
