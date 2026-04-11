from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.agent_config_service import get_llm_client_for_agent
from app.services.llm_client_service import LlmClientError


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


def generate_diagram_svg(
    question_text: str,
    *,
    diagram_image_bytes: Optional[bytes] = None,
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

    if not system_prompt or not user_template:
        logger.warning("diagram_svg agent is missing prompts in database")
        return None

    user_content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": user_template.replace("{question_text}", (question_text or "").strip()[:560]),
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
        "model": agent_config.model,
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
        message_content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return _extract_svg(message_content)
    except LlmClientError as exc:
        logger.warning("Diagram svg generation failed: %s", str(exc))
        return None
