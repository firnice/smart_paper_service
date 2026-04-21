from __future__ import annotations

import base64
import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.agent_config_service import get_llm_client_for_agent
from app.services.llm_client_service import LlmClientError, LlmHttpError


class DiagramSvgUpstreamError(RuntimeError):
    """Raised when upstream SVG generation failed after all retries/fallbacks."""


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


def _build_model_candidates(primary_model: str, fallback_models: list[str]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for raw in [primary_model, *fallback_models]:
        model_name = str(raw or "").strip()
        if not model_name or model_name in seen:
            continue
        seen.add(model_name)
        candidates.append(model_name)
    return candidates


def _is_resource_exhausted_error(body: str) -> bool:
    text = str(body or "")
    lowered = text.lower()
    if "resource_exhausted" in lowered or "resource has been exhausted" in lowered:
        return True
    if "quota" in lowered and ("exceed" in lowered or "exhaust" in lowered):
        return True
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    error_payload = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error_payload, dict):
        return False
    error_message = str(error_payload.get("message") or "").lower()
    error_status = str(error_payload.get("status") or "").upper()
    return error_status == "RESOURCE_EXHAUSTED" or "resource has been exhausted" in error_message


def _build_upstream_error_message(exc: LlmClientError) -> str:
    if isinstance(exc, LlmHttpError):
        if _is_resource_exhausted_error(exc.body):
            return "SVG 图示生成额度已耗尽，请稍后重试。"
        if exc.status_code >= 500:
            return "SVG 图示生成服务暂时不可用，请稍后重试。"
        return f"SVG 图示生成请求失败（{exc.status_code}）。"
    return "SVG 图示生成请求失败，请稍后重试。"


def _normalize_svg_text(latest_svg: Optional[str]) -> Optional[str]:
    svg = _extract_svg(latest_svg)
    if not svg:
        return None
    return svg[:4000]


def _normalize_reference_content_type(content_type: Optional[str]) -> str:
    normalized = str(content_type or "").strip().lower()
    if normalized.startswith("image/"):
        return normalized
    return "image/png"


def _build_user_prompt_text(
    user_template: str,
    question_text: str,
    has_seed_image: bool,
    *,
    custom_prompt: Optional[str] = None,
    latest_svg: Optional[str] = None,
) -> str:
    text = user_template.replace("{question_text}", (question_text or "").strip()[:560]).strip()
    parts = [text]

    if has_seed_image:
        parts.append(
            "如果已提供题目中的原图/图例截图，请优先参考截图里的图形结构、布局和相对位置来生成 SVG。"
            "尽量模仿题目中的图例，不要把重点放在题目文字描述上。"
        )

    normalized_latest_svg = _normalize_svg_text(latest_svg)
    if normalized_latest_svg:
        parts.append(
            "下面是当前最新一版 SVG，请基于这版做增量修改，不要脱离现有图形结构完全重画；"
            "如果它与原图冲突，以原图为准修正。\n"
            f"{normalized_latest_svg}"
        )

    normalized_custom_prompt = (custom_prompt or "").strip()
    if normalized_custom_prompt:
        parts.append(f"本次额外修改要求：\n{normalized_custom_prompt[:1200]}")

    return "\n\n".join(part for part in parts if part)


def generate_diagram_svg(
    question_text: str,
    *,
    reference_images: Optional[list[tuple[bytes, str]]] = None,
    latest_svg: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    trace_id: str = "",
    db: Optional[Session] = None,
) -> Optional[str]:
    if db is None:
        logger.warning("generate_diagram_svg requires a db session")
        return None

    agent_result = get_llm_client_for_agent(db, "diagram_svg")
    if not agent_result:
        logger.warning("diagram_svg agent unavailable")
        return None

    llm_client, agent_config = agent_result
    system_prompt = (agent_config.system_prompt or "").strip()
    user_template = (agent_config.user_prompt_template or "").strip()
    model_candidates = _build_model_candidates(agent_config.model, agent_config.fallback_models)

    if not system_prompt or not user_template:
        logger.warning("diagram_svg agent is missing prompts in database")
        return None
    if not model_candidates:
        logger.warning("diagram_svg agent has no available models")
        return None

    normalized_reference_images = [
        (image_bytes, _normalize_reference_content_type(content_type))
        for image_bytes, content_type in (reference_images or [])
        if image_bytes
    ]

    user_content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": _build_user_prompt_text(
                user_template,
                question_text,
                bool(normalized_reference_images),
                custom_prompt=custom_prompt,
                latest_svg=latest_svg,
            ),
        }
    ]
    for image_bytes, content_type in normalized_reference_images:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{encoded}",
                    "detail": "low",
                },
            }
        )

    last_error: Optional[LlmClientError] = None
    total_attempts = len(model_candidates)
    for attempt, model_name in enumerate(model_candidates, start=1):
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": agent_config.temperature,
        }
        try:
            body = llm_client.chat_completions(
                payload,
                trace_id=trace_id or "diagram_svg",
            )
        except LlmClientError as exc:
            last_error = exc
            logger.warning(
                "Diagram svg generation failed attempt=%d/%d model=%s err=%s",
                attempt,
                total_attempts,
                model_name,
                str(exc),
            )
            if attempt < total_attempts:
                continue
            raise DiagramSvgUpstreamError(_build_upstream_error_message(exc)) from exc

        message_content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        svg = _extract_svg(message_content)
        if svg:
            if attempt > 1:
                logger.info(
                    "Diagram svg fallback succeeded attempt=%d/%d model=%s",
                    attempt,
                    total_attempts,
                    model_name,
                )
            return svg

        logger.warning(
            "Diagram svg response missing valid svg attempt=%d/%d model=%s",
            attempt,
            total_attempts,
            model_name,
        )

    if last_error:
        raise DiagramSvgUpstreamError(_build_upstream_error_message(last_error)) from last_error
    return None
