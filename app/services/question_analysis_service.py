from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.agent_config_service import get_llm_client_for_agent
from app.services.llm_client_service import (
    LlmClientError,
    get_siliconflow_client,
)

_SYSTEM_PROMPT = (
    "你是一个小学/初中错题分析助手。根据题目内容，推断学科、错题分类和可能的错误原因。"
    "仅返回严格 JSON，不要输出任何其他内容。"
)

_USER_PROMPT_TEMPLATE = """\
学生年级：{grade}

题目内容：
{question_text}

请根据题目内容分析并返回 JSON，包含以下字段：
- subject: 学科，只能是以下之一：数学、语文、英语、科学
- category: 错题分类，只能是以下之一：概念不清、计算失误、审题错误、步骤缺失、知识点混淆
- error_reason: 最可能的错误原因，只能是以下之一：公式记忆错误、概念边界不清、进位借位出错、抄写数字错误、漏看条件、单位忽略、过程跳步、校验缺失、题型混淆、方法选择不当
- title: 为这道错题起一个简短的标题（不超过15个字），概括题目考查的知识点

示例返回：
{{"subject": "数学", "category": "计算失误", "error_reason": "进位借位出错", "title": "两位数加法进位"}}"""


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

    # 优先使用 agent 配置
    agent_result = get_llm_client_for_agent(db, "question_analyze") if db else None
    if agent_result:
        llm_client, agent_config = agent_result
        model = agent_config.model
        system_prompt = agent_config.system_prompt or _SYSTEM_PROMPT
        user_template = agent_config.user_prompt_template or _USER_PROMPT_TEMPLATE
        temperature = agent_config.temperature
    else:
        # 回退到旧方式
        client = get_siliconflow_client()
        if not client or not client.default_model:
            logger.warning("No siliconflow client available for question analysis")
            return None
        llm_client = client.base_client
        model = client.default_model
        system_prompt = _SYSTEM_PROMPT
        user_template = _USER_PROMPT_TEMPLATE
        temperature = 0.1

    grade_display = grade or "未知"
    user_prompt = user_template.format(
        grade=grade_display,
        question_text=question_text.strip(),
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
