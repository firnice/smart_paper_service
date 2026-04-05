import base64
import http.client
from io import BytesIO
import json
import re
import time
from typing import Optional

from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.core.ocr_extract_llm_config import load_ocr_extract_llm_config
from app.core.logger import logger
from app.schemas.common import ImageBox
from app.schemas.ocr import OcrItem
from app.services.llm_client_service import (
    BaseLlmClient,
    LlmClientError,
    LlmHttpError,
    LlmNetworkError,
    get_siliconflow_client,
)

REFINE_SYSTEM_PROMPT = (
    "你是一个试卷图示定位助手。"
    "只找出题目中用于解题的印刷图示区域。"
    "必须严格排除手写答案、铅笔圈画、红笔批改痕迹和大块空白边缘。"
)

REFINE_USER_PROMPT = (
    "请在这张题目截图中定位干净的印刷图示区域。"
    "只返回一个 JSON 对象，键名必须是 diagram_box。"
    "格式为：{\"diagram_box\": {\"ymin\": int, \"xmin\": int, \"ymax\": int, \"xmax\": int}}。"
    "如果不存在印刷图示，请返回 {\"diagram_box\": null}。"
    "坐标必须使用当前这张截图的像素坐标。"
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


def _to_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "是", "对"}:
        return True
    if text in {"false", "0", "no", "n", "否", "错", "null", "none", ""}:
        return False
    return default


def _normalize_optional_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none"}:
        return None
    return text


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
        is_wrong = _to_bool(raw.get("is_wrong"), default=False)
        wrong_reason = _normalize_optional_text(raw.get("wrong_reason"))
        correction_suggestion = _normalize_optional_text(raw.get("correction_suggestion"))
        if not is_wrong:
            wrong_reason = None
            correction_suggestion = None
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
        item_id = number or index
        items.append(
            OcrItem(
                id=item_id,
                text=text_value,
                subject_tag=_normalize_optional_text(raw.get("subject_tag")),
                is_wrong=is_wrong,
                wrong_reason=wrong_reason,
                correction_suggestion=correction_suggestion,
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


def resolve_extract_prompt(custom_prompt: Optional[str]) -> tuple[str, Optional[str]]:
    config = load_ocr_extract_llm_config()
    normalized_prompt = (custom_prompt or "").strip() or None
    if not normalized_prompt:
        return config.user_prompt, None
    effective_prompt = f"{config.user_prompt}\n\n{config.custom_prompt_prefix}\n{normalized_prompt}"
    return effective_prompt, normalized_prompt


def _call_vision_completion(
    image_bytes: bytes,
    content_type: str,
    file_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    db: Optional[Session] = None,
) -> str:
    config = load_ocr_extract_llm_config()
    client = get_siliconflow_client()
    if not client:
        logger.error("OCR LLM config missing. Please set SILICONFLOW_API_KEY and SILICONFLOW_BASE_URL.")
        raise RuntimeError("SILICONFLOW LLM config missing.")
    if config.provider != "siliconflow":
        raise RuntimeError(f"Unsupported OCR LLM provider: {config.provider}")
    if not config.model:
        raise RuntimeError("OCR extract YAML missing model.")
    llm_client = BaseLlmClient(
        provider="siliconflow",
        base_url=client.base_client.base_url,
        api_key=client.base_client.api_key,
        timeout_seconds=config.timeout_seconds or client.base_client.timeout_seconds,
    )
    model_name = config.model
    timeout_seconds = llm_client.timeout_seconds

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
            "model": model_name,
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
            "OCR-LLM request start attempt=%d/%d tag=%s model=%s bytes=%d detail=%s filename=%s timeout=%ss",
            index,
            total_attempts,
            tag,
            model_name,
            len(candidate_bytes),
            detail,
            file_name,
            timeout_seconds,
        )
        start_time = time.monotonic()

        try:
            body = llm_client.chat_completions(
                payload,
                trace_id=f"ocr_llm:{file_name}:{tag}:{index}",
            )
            content = (
                body.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            elapsed = time.monotonic() - start_time
            logger.info(
                "OCR-LLM response received attempt=%d/%d tag=%s length=%d elapsed=%.2fs",
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
            has_next_retry = index < len(retry_candidates)
            logger.error(
                "OCR-LLM HTTP error attempt=%d/%d tag=%s status=%s retryable=%s elapsed=%.2fs body=%s",
                index,
                total_attempts,
                tag,
                exc.status_code,
                retryable and has_next_retry,
                elapsed,
                body_text,
            )
            if retryable and has_next_retry:
                continue
            if retryable:
                last_error_message = "识别大模型暂时异常，请稍后重试。"
            else:
                last_error_message = f"OCR-LLM request failed ({exc.status_code})."
            raise RuntimeError(last_error_message) from exc
        except (LlmNetworkError, http.client.RemoteDisconnected, ConnectionError) as exc:
            elapsed = time.monotonic() - start_time
            has_next_retry = index < len(retry_candidates)
            logger.warning(
                "OCR-LLM timeout/network error attempt=%d/%d tag=%s retryable=%s elapsed=%.2fs err=%s",
                index,
                total_attempts,
                tag,
                has_next_retry,
                elapsed,
                str(exc),
            )
            if has_next_retry:
                continue
            last_error_message = (
                "识别大模型请求失败或超时，请重试，或更换更小的图片。"
            )
            raise RuntimeError(last_error_message) from exc
        except LlmClientError as exc:
            raise RuntimeError(f"OCR-LLM request failed: {str(exc)}") from exc

    raise RuntimeError(last_error_message)


def extract_questions(
    image_bytes: bytes,
    content_type: str,
    file_name: str,
    prompt: Optional[str] = None,
    db: Optional[Session] = None,
) -> tuple[list[OcrItem], str]:
    """Call a multimodal LLM to extract and analyze questions from the paper image."""
    config = load_ocr_extract_llm_config()
    effective_prompt, custom_prompt = resolve_extract_prompt(prompt)
    logger.info(
        "OCR prompt resolved file=%s custom_prompt=%r effective_prompt=%r",
        file_name,
        custom_prompt,
        effective_prompt,
    )
    content = _call_vision_completion(
        image_bytes=image_bytes,
        content_type=content_type,
        file_name=file_name,
        system_prompt=config.system_prompt,
        user_prompt=effective_prompt,
        temperature=config.temperature,
        db=db,
    )
    items = _parse_items(content)
    logger.info("OCR-LLM parsed items=%d", len(items))
    if not items and content.strip():
        return (
            [
                OcrItem(
                    id=1,
                    text=content.strip(),
                    subject_tag=None,
                    is_wrong=False,
                    wrong_reason=None,
                    correction_suggestion=None,
                    has_image=False,
                    image_box=None,
                )
            ],
            effective_prompt,
        )
    return items, effective_prompt


def refine_diagram_box(
    image_bytes: bytes,
    content_type: str,
    file_name: str,
    db: Optional[Session] = None,
) -> Optional[ImageBox]:
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
        db=db,
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
