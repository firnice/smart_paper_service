import base64
import http.client
from io import BytesIO
import json
import logging
import re
import time
from typing import Optional

from PIL import Image, ImageOps

from app.schemas.common import ImageBox
from app.schemas.ocr import OcrItem
from app.services.llm_client_service import (
    LlmClientError,
    LlmHttpError,
    LlmNetworkError,
    get_siliconflow_client,
)


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
    "question_box (object {ymin,xmin,ymax,xmax} in ORIGINAL IMAGE PIXELS; include question stem/options/diagram), "
    "image_box (object with keys ymin,xmin,ymax,xmax in ORIGINAL IMAGE PIXELS, or null). "
    "Do NOT return [x1,y1,x2,y2] array order. "
    "If a question includes a necessary illustration/diagram, set has_image=true and return a "
    "best-effort image_box around the diagram."
)

REFINE_SYSTEM_PROMPT = (
    "You are a worksheet diagram locator. "
    "Find only the printed figure region used to solve the question. "
    "Strictly exclude handwritten answers, pencil circles, red correction marks, and blank margins."
)

REFINE_USER_PROMPT = (
    "Locate the clean printed diagram area in this question snapshot. "
    "Return ONLY one JSON object with key diagram_box. "
    "Format: {\"diagram_box\": {\"ymin\": int, \"xmin\": int, \"ymax\": int, \"xmax\": int}}. "
    "If no printed diagram exists, return {\"diagram_box\": null}. "
    "Coordinates must be in CURRENT IMAGE pixels."
)

RETRYABLE_UPSTREAM_CODE_MARKERS = ("50507", "unknown error")
OCR_RETRY_MAX_SIDE = 2048
OCR_RETRY_QUALITY = 88


def _is_retryable_ocr_http_error(status_code: int, body: str) -> bool:
    if status_code >= 500:
        return True
    lowered = (body or "").lower()
    return any(marker in lowered for marker in RETRYABLE_UPSTREAM_CODE_MARKERS)


def _downscale_for_ocr(image_bytes: bytes, max_side: int = OCR_RETRY_MAX_SIDE) -> tuple[bytes, str]:
    """
    Create a JPEG retry candidate with bounded resolution and size.
    """
    with Image.open(BytesIO(image_bytes)) as img:
        normalized = ImageOps.exif_transpose(img)
        if normalized.mode != "RGB":
            normalized = normalized.convert("RGB")

        width, height = normalized.size
        max_len = max(width, height)
        if max_len > max_side:
            ratio = max_side / float(max_len)
            target_width = max(1, int(width * ratio))
            target_height = max(1, int(height * ratio))
            normalized = normalized.resize((target_width, target_height), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        normalized.save(buffer, format="JPEG", quality=OCR_RETRY_QUALITY, optimize=True)
        buffer.seek(0)
        return buffer.read(), "image/jpeg"


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
        question_box = _to_image_box(
            raw.get("question_box")
            or raw.get("question_bbox")
            or raw.get("question_region")
            or raw.get("bbox_question")
        )
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
                question_box=question_box,
                image_box=image_box,
            )
        )
    return items


def _parse_refine_box(text: str) -> Optional[ImageBox]:
    cleaned = _strip_code_fence(text).strip()
    if not cleaned:
        return None

    payload = None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                payload = None

    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return None

    return _to_image_box(
        payload.get("diagram_box")
        or payload.get("image_box")
        or payload.get("bbox")
        or payload.get("box")
    )


def _call_vision_completion(
    image_bytes: bytes,
    content_type: str,
    file_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    client = get_siliconflow_client()
    if not client or not client.ocr_model:
        logger.error("OCR config missing. Please set SILICONFLOW_OCR_MODEL.")
        raise RuntimeError("SILICONFLOW OCR config missing. Please set SILICONFLOW_OCR_MODEL.")

    retry_candidates: list[tuple[str, bytes, str, str]] = [
        ("orig-high", image_bytes, content_type, "high"),
    ]

    try:
        retry_bytes, retry_content_type = _downscale_for_ocr(image_bytes)
        retry_candidates.append(("scaled-high", retry_bytes, retry_content_type, "high"))
        retry_candidates.append(("scaled-low", retry_bytes, retry_content_type, "low"))
    except Exception as exc:
        logger.warning("Failed to build scaled OCR retry candidate: %s", str(exc))
        retry_candidates.append(("orig-low", image_bytes, content_type, "low"))

    total_attempts = len(retry_candidates)
    last_error_message = "OCR request failed."

    for index, (tag, candidate_bytes, candidate_content_type, detail) in enumerate(retry_candidates, start=1):
        encoded = base64.b64encode(candidate_bytes).decode("utf-8")
        data_url = f"data:{candidate_content_type};base64,{encoded}"
        payload = {
            "model": client.ocr_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url, "detail": detail}},
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
            "temperature": temperature,
        }

        logger.info(
            "OCR request start attempt=%d/%d tag=%s model=%s bytes=%d detail=%s filename=%s timeout=%ss",
            index,
            total_attempts,
            tag,
            client.ocr_model,
            len(candidate_bytes),
            detail,
            file_name,
            client.base_client.timeout_seconds,
        )
        start_time = time.monotonic()

        try:
            body = client.base_client.chat_completions(
                payload,
                trace_id=f"ocr:{file_name}:{tag}:{index}",
            )
            content = (
                body.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            elapsed = time.monotonic() - start_time
            logger.info(
                "OCR response received attempt=%d/%d tag=%s length=%d elapsed=%.2fs",
                index,
                total_attempts,
                tag,
                len(content),
                elapsed,
            )
            return content
        except LlmHttpError as exc:
            body_text = exc.body
            elapsed = time.monotonic() - start_time
            retryable = _is_retryable_ocr_http_error(exc.status_code, body_text)
            has_next = index < total_attempts
            logger.error(
                "OCR HTTP error attempt=%d/%d tag=%s status=%s retryable=%s elapsed=%.2fs body=%s",
                index,
                total_attempts,
                tag,
                exc.status_code,
                retryable and has_next,
                elapsed,
                body_text,
            )
            if retryable and has_next:
                continue
            if retryable:
                last_error_message = "OCR 上游服务暂时异常，请稍后重试。"
            else:
                last_error_message = f"OCR request failed ({exc.status_code})."
            raise RuntimeError(last_error_message) from exc
        except (LlmNetworkError, http.client.RemoteDisconnected, ConnectionError) as exc:
            elapsed = time.monotonic() - start_time
            has_next = index < total_attempts
            logger.warning(
                "OCR request timeout/network error attempt=%d/%d tag=%s retryable=%s elapsed=%.2fs err=%s",
                index,
                total_attempts,
                tag,
                has_next,
                elapsed,
                str(exc),
            )
            if has_next:
                continue
            last_error_message = (
                "OCR request failed or timed out. Try again, use a smaller image, "
                "or increase SILICONFLOW_TIMEOUT_SECONDS."
            )
            raise RuntimeError(last_error_message) from exc
        except LlmClientError as exc:
            raise RuntimeError(f"OCR request failed: {str(exc)}") from exc

    raise RuntimeError(last_error_message)


def extract_questions(image_bytes: bytes, content_type: str, file_name: str) -> list[OcrItem]:
    """Call SiliconFlow vision model to extract questions."""
    content = _call_vision_completion(
        image_bytes=image_bytes,
        content_type=content_type,
        file_name=file_name,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT,
        temperature=0.2,
    )
    items = _parse_items(content)
    logger.info("OCR parsed items=%d", len(items))
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


def refine_diagram_box(image_bytes: bytes, content_type: str, file_name: str) -> Optional[ImageBox]:
    """
    Second-pass refinement for printed diagram region.
    Input should be one question snapshot.
    """
    content = _call_vision_completion(
        image_bytes=image_bytes,
        content_type=content_type,
        file_name=file_name,
        system_prompt=REFINE_SYSTEM_PROMPT,
        user_prompt=REFINE_USER_PROMPT,
        temperature=0.0,
    )
    box = _parse_refine_box(content)
    if box:
        logger.info(
            "Refine diagram box parsed: (%d,%d,%d,%d)",
            box.ymin,
            box.xmin,
            box.ymax,
            box.xmax,
        )
    else:
        logger.info("Refine diagram box not found")
    return box
