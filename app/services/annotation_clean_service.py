import base64
import json
import logging
from typing import Any, Optional
from urllib import error, request

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


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
    req = request.Request(
        settings.annotation_clean_api_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **(
                {"Authorization": f"Bearer {settings.annotation_clean_api_key}"}
                if settings.annotation_clean_api_key
                else {}
            ),
        },
        method="POST",
    )

    timeout_seconds = max(3, int(settings.annotation_clean_timeout_seconds))
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        payload = json.loads(raw)
        encoded = _extract_clean_image_base64(payload)
        if not encoded:
            logger.warning("Annotation clean SaaS response missing clean image field")
            return None
        return base64.b64decode(encoded)
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Annotation clean SaaS request failed: %s", str(exc))
        return None
