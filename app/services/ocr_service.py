import base64
import json
import logging
import re
import time
from typing import Optional
from urllib import error, request

from app.core.llm_settings import load_llm_settings
from app.schemas.common import ImageBox
from app.schemas.ocr import OcrItem


logger = logging.getLogger("uvicorn.error")

SYSTEM_PROMPT = (
    "You are a primary school worksheet digitizer. "
    "Extract printed questions only and ignore handwritten answers, markings, and corrections. "
    "Preserve the original reading order (top-to-bottom, left-to-right) and keep line breaks "
    "and numbering as seen on the page."
)

USER_PROMPT = (
    "Extract all questions from the image. Return ONLY a JSON array in reading order. "
    "Each item must have: "
    "id (int, use the printed question number if present), "
    "text (string, include the question number and preserve line breaks), "
    "has_image (bool), "
    "image_box (list [ymin, xmin, ymax, xmax] in ORIGINAL IMAGE PIXELS, or null). "
    "If a question includes a necessary illustration/diagram, set has_image=true and return a "
    "best-effort image_box around the diagram."
)


def _to_image_box(value: object) -> Optional[ImageBox]:
    if isinstance(value, ImageBox):
        return value

    if isinstance(value, dict):
        keys = {key.lower(): value.get(key) for key in value.keys()}
        if {"ymin", "xmin", "ymax", "xmax"} <= keys.keys():
            try:
                return ImageBox(
                    ymin=max(0, int(keys["ymin"])),
                    xmin=max(0, int(keys["xmin"])),
                    ymax=max(0, int(keys["ymax"])),
                    xmax=max(0, int(keys["xmax"])),
                )
            except (TypeError, ValueError):
                return None

        for candidate in (("y1", "x1", "y2", "x2"), ("top", "left", "bottom", "right")):
            if set(candidate) <= keys.keys():
                try:
                    y1, x1, y2, x2 = (keys[name] for name in candidate)
                    return ImageBox(
                        ymin=max(0, int(y1)),
                        xmin=max(0, int(x1)),
                        ymax=max(0, int(y2)),
                        xmax=max(0, int(x2)),
                    )
                except (TypeError, ValueError):
                    return None

        try:
            return ImageBox(
                ymin=max(0, int(value.get("ymin", 0))),
                xmin=max(0, int(value.get("xmin", 0))),
                ymax=max(0, int(value.get("ymax", 0))),
                xmax=max(0, int(value.get("xmax", 0))),
            )
        except (TypeError, ValueError):
            return None

    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            ymin, xmin, ymax, xmax = value
            return ImageBox(
                ymin=max(0, int(ymin)),
                xmin=max(0, int(xmin)),
                ymax=max(0, int(ymax)),
                xmax=max(0, int(xmax)),
            )
        except (TypeError, ValueError):
            return None
    return None


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3].strip()
    return cleaned


def _extract_number(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if match:
        try:
            return int(match.group(0))
        except ValueError:
            return None
    return None


def _ensure_numbered(text: str, number: Optional[int]) -> str:
    if not number:
        return text
    if re.match(r"^\s*\d+[\.\、\)]", text):
        return text
    return f"{number}. {text}"


def _parse_items(text: str) -> list[OcrItem]:
    cleaned = _strip_code_fence(text).strip()
    if not cleaned:
        return []

    payload = None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[(.*)\]", cleaned, re.DOTALL)
        if match:
            try:
                payload = json.loads(f"[{match.group(1)}]")
            except json.JSONDecodeError:
                payload = None

    if not isinstance(payload, list):
        return []

    items: list[OcrItem] = []
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            continue
        text_value = str(raw.get("text", "")).strip()
        if not text_value:
            continue
        number = _extract_number(
            raw.get("id")
            or raw.get("number")
            or raw.get("question_no")
            or raw.get("question_number")
        )
        if number:
            text_value = _ensure_numbered(text_value, number)
        has_image = bool(raw.get("has_image", False))
        image_box = _to_image_box(
            raw.get("image_box")
            or raw.get("bbox")
            or raw.get("box")
            or raw.get("image_bbox")
        )
        if image_box:
            has_image = True
        items.append(
            OcrItem(
                id=number or int(raw.get("id", index)),
                text=text_value,
                has_image=has_image,
                image_box=image_box,
            )
        )
    return items


def extract_questions(image_bytes: bytes, content_type: str, file_name: str) -> list[OcrItem]:
    """Call SiliconFlow vision model to extract questions."""
    settings = load_llm_settings()
    if not settings or not settings.ocr_model:
        logger.error("OCR config missing. Please set SILICONFLOW_OCR_MODEL.")
        raise RuntimeError("SILICONFLOW OCR config missing. Please set SILICONFLOW_OCR_MODEL.")

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{content_type};base64,{encoded}"

    detail = "high"
    logger.info(
        "OCR request start model=%s bytes=%d detail=%s filename=%s timeout=%ss base_url=%s",
        settings.ocr_model,
        len(image_bytes),
        detail,
        file_name,
        settings.timeout_seconds,
        settings.base_url,
    )
    start_time = time.monotonic()

    payload = {
        "model": settings.ocr_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url, "detail": detail}},
                    {"type": "text", "text": USER_PROMPT},
                ],
            },
        ],
        "temperature": 0.2,
    }

    data = json.dumps(payload).encode("utf-8")
    api_url = f"{settings.base_url}/chat/completions"
    req = request.Request(
        api_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=settings.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        logger.error("OCR HTTP error %s: %s", exc.code, detail)
        raise RuntimeError(f"OCR request failed ({exc.code}): {detail}") from exc
    except (TimeoutError, error.URLError) as exc:
        logger.exception("OCR request timed out or failed")
        raise RuntimeError(
            "OCR request timed out. Try a smaller image or increase SILICONFLOW_TIMEOUT_SECONDS."
        ) from exc

    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    items = _parse_items(content)
    elapsed = time.monotonic() - start_time
    logger.info(
        "OCR response received length=%d items=%d elapsed=%.2fs",
        len(content),
        len(items),
        elapsed,
    )
    if not items and content.strip():
        return [
            OcrItem(
                id=1,
                text=content.strip(),
                has_image=False,
                image_box=None,
            )
        ]
    return items
