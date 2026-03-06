from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from app.schemas.common import ImageBox
from app.services.image_service import crop_image, get_image_size, has_meaningful_content, normalize_image_box_for_source
from app.services.llm_client_service import LlmClientError, get_whatai_client


logger = logging.getLogger("uvicorn.error")

_CROP_SYSTEM_PROMPT = (
    "You are a worksheet diagram detector. "
    "Return strict JSON only."
)

_CROP_USER_PROMPT_TEMPLATE = (
    "Locate the core printed diagram area in this question snapshot. "
    "Exclude handwriting marks, score marks, and large blank margins. "
    "Return ONLY JSON: {{\"diagram_box\": {{\"ymin\": int, \"xmin\": int, \"ymax\": int, \"xmax\": int}}}}. "
    "Coordinates must be in CURRENT image pixels. "
    "If diagram not found, return {{\"diagram_box\": null}}. "
    "Question text (for context): {question_text}"
)

_SVG_SYSTEM_PROMPT = (
    "You are an SVG diagram generator for elementary worksheet cards. "
    "Output clean, valid SVG only."
)

_SVG_USER_PROMPT_TEMPLATE = (
    "Generate a simple black-and-white educational diagram as SVG for this question. "
    "Requirements: width around 900, height around 520, white background, black strokes, no script/style tags. "
    "Keep it minimal and readable for students. Return ONLY raw <svg>...</svg>. "
    "Question text: {question_text}"
)


@dataclass(frozen=True)
class DiagramCropResult:
    image_bytes: bytes
    width: int
    height: int
    box: ImageBox
    model: str


def _strip_code_fence(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return cleaned


def _extract_message_text(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        chunks: list[str] = []
        for chunk in message_content:
            if isinstance(chunk, str):
                chunks.append(chunk)
                continue
            if not isinstance(chunk, dict):
                continue
            chunk_type = str(chunk.get("type") or "").lower()
            if chunk_type == "text":
                chunks.append(str(chunk.get("text", "")))
            elif "text" in chunk:
                chunks.append(str(chunk.get("text", "")))
        return "\n".join(chunks)
    return str(message_content or "")


def _to_image_box(value: Any) -> Optional[ImageBox]:
    if isinstance(value, ImageBox):
        return value
    if isinstance(value, dict):
        keys = {str(key).lower(): value.get(key) for key in value.keys()}
        if {"ymin", "xmin", "ymax", "xmax"} <= set(keys.keys()):
            try:
                return ImageBox(
                    ymin=max(0, int(keys["ymin"])),
                    xmin=max(0, int(keys["xmin"])),
                    ymax=max(0, int(keys["ymax"])),
                    xmax=max(0, int(keys["xmax"])),
                )
            except (TypeError, ValueError):
                return None
        if {"y1", "x1", "y2", "x2"} <= set(keys.keys()):
            try:
                return ImageBox(
                    ymin=max(0, int(keys["y1"])),
                    xmin=max(0, int(keys["x1"])),
                    ymax=max(0, int(keys["y2"])),
                    xmax=max(0, int(keys["x2"])),
                )
            except (TypeError, ValueError):
                return None
        return None
    return None


def _parse_diagram_box(content: Any) -> Optional[ImageBox]:
    text = _strip_code_fence(_extract_message_text(content))
    if not text:
        return None
    payload: Any = None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    if payload.get("diagram_box") is None:
        return None
    return _to_image_box(payload.get("diagram_box") or payload.get("image_box") or payload.get("bbox"))


def _extract_svg(content: Any) -> Optional[str]:
    text = _strip_code_fence(_extract_message_text(content))
    if not text:
        return None
    match = re.search(r"<svg[\s\S]*?</svg>", text, re.IGNORECASE)
    if not match:
        return None
    svg = match.group(0).strip()
    if "<script" in svg.lower() or "<style" in svg.lower():
        return None
    return svg


def generate_diagram_crop(
    question_image_bytes: bytes,
    *,
    question_text: str = "",
    content_type: str = "image/png",
    trace_id: str = "",
) -> Optional[DiagramCropResult]:
    client = get_whatai_client()
    if not client or not client.diagram_crop_model:
        return None

    encoded = base64.b64encode(question_image_bytes).decode("utf-8")
    data_url = f"data:{content_type};base64,{encoded}"
    payload = {
        "model": client.diagram_crop_model,
        "messages": [
            {"role": "system", "content": _CROP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                    {
                        "type": "text",
                        "text": _CROP_USER_PROMPT_TEMPLATE.format(
                            question_text=(question_text or "").strip()[:320]
                        ),
                    },
                ],
            },
        ],
        "temperature": 0.0,
    }

    try:
        body = client.base_client.chat_completions(
            payload,
            trace_id=trace_id or "whatai_diagram_crop",
        )
        message_content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        raw_box = _parse_diagram_box(message_content)
        if not raw_box:
            return None
        image_w, image_h = get_image_size(question_image_bytes)
        normalized_box = normalize_image_box_for_source(raw_box, image_w, image_h)
        if not normalized_box:
            return None
        cropped_bytes, out_w, out_h = crop_image(
            question_image_bytes,
            normalized_box.ymin,
            normalized_box.xmin,
            normalized_box.ymax,
            normalized_box.xmax,
            max_size=None,
        )
        if not has_meaningful_content(cropped_bytes):
            return None
        return DiagramCropResult(
            image_bytes=cropped_bytes,
            width=out_w,
            height=out_h,
            box=normalized_box,
            model=client.diagram_crop_model,
        )
    except (LlmClientError, ValueError) as exc:
        logger.warning("Whatai diagram crop failed: %s", str(exc))
        return None


def generate_diagram_svg(
    question_text: str,
    *,
    diagram_image_bytes: Optional[bytes] = None,
    trace_id: str = "",
) -> Optional[str]:
    client = get_whatai_client()
    if not client or not client.diagram_svg_model:
        return None

    user_content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": _SVG_USER_PROMPT_TEMPLATE.format(question_text=(question_text or "").strip()[:560]),
        }
    ]
    if diagram_image_bytes:
        encoded = base64.b64encode(diagram_image_bytes).decode("utf-8")
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encoded}",
                    "detail": "low",
                },
            }
        )

    payload = {
        "model": client.diagram_svg_model,
        "messages": [
            {"role": "system", "content": _SVG_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }

    try:
        body = client.base_client.chat_completions(
            payload,
            trace_id=trace_id or "whatai_diagram_svg",
        )
        message_content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return _extract_svg(message_content)
    except LlmClientError as exc:
        logger.warning("Whatai diagram svg generation failed: %s", str(exc))
        return None
