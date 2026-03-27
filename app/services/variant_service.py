from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.agent_config_service import get_llm_client_for_agent
from app.services.llm_client_service import LlmClientError, get_siliconflow_client


# ---------------------------------------------------------------------------
# 旧版英文 prompt（保持向后兼容）
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a primary school math tutor. "
    "Generate variants with the same logic but different numbers or scenarios. "
    "Return ONLY a JSON array of strings."
)

# ---------------------------------------------------------------------------
# 新版中文 prompt 模板（举一反三增强版）
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_CN_TEMPLATE = (
    "你是一位经验丰富的小学{subject}老师。请根据原题出{count}道类似但数字或情境不同的练习题。\n"
    "每道题要有参考答案和一句简短的解题提示。\n"
    '仅返回严格 JSON 数组，格式: [{{"text":"题目","answer":"答案","hint":"提示"}}]'
)


@dataclass
class VariantItem:
    text: str
    answer: str = ""
    hint: str = ""


# ---------------------------------------------------------------------------
# 内部解析工具
# ---------------------------------------------------------------------------


def _parse_variants(text: str, count: int) -> list[str]:
    """解析旧版返回格式：纯字符串数组。"""
    cleaned = text.strip()
    if not cleaned:
        return []

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:count]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[(.*)\]", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(f"[{match.group(1)}]")
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()][:count]
        except json.JSONDecodeError:
            pass

    lines = [line.strip() for line in re.split(r"[\r\n]+", cleaned) if line.strip()]
    lines = [re.sub(r"^\d+[\).\s]+", "", line).strip() for line in lines]
    return lines[:count]


def _parse_variant_items(text: str, count: int) -> list[VariantItem]:
    """解析新版返回格式：包含 text/answer/hint 的对象数组。"""
    cleaned = text.strip()
    if not cleaned:
        return []

    # 尝试直接解析
    parsed = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # 尝试提取 JSON 数组部分
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    if isinstance(parsed, list):
        items = []
        for obj in parsed[:count]:
            if isinstance(obj, dict):
                items.append(VariantItem(
                    text=str(obj.get("text", "")).strip(),
                    answer=str(obj.get("answer", "")).strip(),
                    hint=str(obj.get("hint", "")).strip(),
                ))
            elif isinstance(obj, str):
                items.append(VariantItem(text=obj.strip()))
        return [item for item in items if item.text]

    return []


# ---------------------------------------------------------------------------
# 获取 LLM 客户端的辅助函数
# ---------------------------------------------------------------------------


def _get_client_and_model(db: Optional[Session] = None):
    """
    优先使用 agent 配置获取客户端，回退到旧的 get_siliconflow_client()。
    返回 (base_client, model, temperature)。
    """
    # 优先: agent 配置
    if db is not None:
        result = get_llm_client_for_agent(db, "question_generate")
        if result:
            client, config = result
            logger.info(
                "variant_service: using agent config (provider=%s, model=%s)",
                config.provider, config.model,
            )
            return client, config.model, config.temperature

    # 回退: 旧的硬编码方式
    sf_client = get_siliconflow_client()
    if not sf_client or not sf_client.default_model:
        raise RuntimeError("SILICONFLOW config missing. Please set SILICONFLOW_MODEL.")
    return sf_client.base_client, sf_client.default_model, 0.7


# ---------------------------------------------------------------------------
# 旧版接口（保持向后兼容）
# ---------------------------------------------------------------------------


def generate_variants(
    source_text: str,
    count: int = 3,
    grade: Optional[str] = None,
    subject: Optional[str] = None,
    db: Optional[Session] = None,
) -> list[str]:
    """Generate same-type variants via LLM (agent config or SiliconFlow fallback)."""
    base_client, model, temperature = _get_client_and_model(db)

    user_prompt = f"Source question: {source_text}\n"
    if grade:
        user_prompt += f"Grade: {grade}\n"
    if subject:
        user_prompt += f"Subject: {subject}\n"
    user_prompt += f"Return {count} variants."

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    try:
        body = base_client.chat_completions(
            payload,
            trace_id="variant_generate",
        )
    except LlmClientError as exc:
        raise RuntimeError(f"LLM request failed: {str(exc)}") from exc

    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    variants = _parse_variants(content, count)
    if not variants and content.strip():
        return [content.strip()]
    return variants


# ---------------------------------------------------------------------------
# 新版接口（结构化返回）
# ---------------------------------------------------------------------------


def generate_variants_for_question(
    source_text: str,
    count: int = 3,
    grade: Optional[str] = None,
    subject: Optional[str] = None,
    db: Optional[Session] = None,
) -> list[VariantItem]:
    """
    增强版举一反三：生成结构化的练习题（包含题目、答案、提示）。
    """
    base_client, model, temperature = _get_client_and_model(db)

    subject_name = subject or "数学"
    system_prompt = SYSTEM_PROMPT_CN_TEMPLATE.format(subject=subject_name, count=count)

    user_prompt = f"原题：{source_text}\n"
    if grade:
        user_prompt += f"年级：{grade}\n"
    user_prompt += f"请出{count}道类似的练习题。"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    try:
        body = base_client.chat_completions(
            payload,
            trace_id="variant_generate_for_question",
        )
    except LlmClientError as exc:
        logger.exception("generate_variants_for_question LLM request failed")
        raise RuntimeError(f"LLM request failed: {str(exc)}") from exc

    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    items = _parse_variant_items(content, count)
    if not items and content.strip():
        # 降级：把整个内容作为一道题
        items = [VariantItem(text=content.strip())]

    return items
