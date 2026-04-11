from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.agent_config_service import get_llm_client_for_agent
from app.services.llm_client_service import LlmClientError


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return cleaned


def _parse_analysis_json(text: str) -> Optional[dict[str, Any]]:
    cleaned = _strip_code_fence(text)
    if not cleaned:
        return None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None

    return {
        "subject": str(payload.get("subject", "")).strip() or None,
        "category": str(payload.get("category", "")).strip() or None,
        "error_reason": str(payload.get("error_reason", "")).strip() or None,
        "title": str(payload.get("title", "")).strip() or None,
    }


def analyze_question(
    question_text: str,
    *,
    grade: str = "",
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    """Analyze a question and suggest subject, category, error_reason, title."""
    if not question_text or not question_text.strip():
        return None

    if db is None:
        logger.warning("analyze_question requires a db session")
        return None

    agent_result = get_llm_client_for_agent(db, "question_analyze")
    if not agent_result:
        logger.warning("question_analyze agent unavailable")
        return None

    llm_client, agent_config = agent_result
    model = agent_config.model
    system_prompt = (agent_config.system_prompt or "").strip()
    user_template = (agent_config.user_prompt_template or "").strip()
    temperature = agent_config.temperature

    if not system_prompt or not user_template:
        logger.warning("question_analyze agent is missing prompts in database")
        return None

    grade_display = grade or "未知"
    user_prompt = (
        user_template
        .replace("{grade}", grade_display)
        .replace("{question_text}", question_text.strip())
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    try:
        data = llm_client.chat_completions(
            payload,
            trace_id="analyze_question",
        )
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            text_chunks: list[str] = []
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    text_chunks.append(str(chunk.get("text", "")))
            parsed = _parse_analysis_json("\n".join(text_chunks))
        else:
            parsed = _parse_analysis_json(str(content or ""))
        if parsed:
            logger.info(
                "Question analysis result: subject=%s category=%s error_reason=%s title=%s",
                parsed.get("subject"),
                parsed.get("category"),
                parsed.get("error_reason"),
                parsed.get("title"),
            )
        return parsed
    except (LlmClientError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Question analysis LLM call failed: %s", str(exc))
        return None
