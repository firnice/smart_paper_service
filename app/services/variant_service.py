from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.agent_config_service import get_llm_client_for_agent
from app.services.diagram_llm_service import generate_diagram_svg
from app.services.llm_client_service import LlmClientError
from app.services.storage_service import get_storage_service

CUSTOM_PROMPT_PREFIX = "补充要求："


@dataclass
class VariantItem:
    text: str
    answer: str = ""
    hint: str = ""
    svg: Optional[str] = None


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


def _request_variant_items(
    *,
    base_client,
    model: str,
    temperature: float,
    system_prompt: str,
    user_prompt: str,
    trace_id: str,
    count: int,
) -> list[VariantItem]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    body = base_client.chat_completions(
        payload,
        trace_id=trace_id,
    )
    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    items = _parse_variant_items(content, count)
    if not items and content.strip():
        return [VariantItem(text=content.strip())]
    return items


# ---------------------------------------------------------------------------
# 获取 LLM 客户端的辅助函数
# ---------------------------------------------------------------------------


def _get_client_and_config(db: Optional[Session]):
    """从 DB agent 配置获取客户端。"""
    if db is None:
        raise RuntimeError("variant_service requires a db session")
    result = get_llm_client_for_agent(db, "question_generate")
    if not result:
        raise RuntimeError("question_generate agent unavailable")
    client, config = result
    system_prompt = (config.system_prompt or "").strip()
    user_template = (config.user_prompt_template or "").strip()
    if not system_prompt or not user_template:
        raise RuntimeError("question_generate agent is missing prompts in database")
    logger.info("variant_service: using agent config provider=%s model=%s", config.provider, config.model)
    return client, config


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
    """Generate same-type variants via LLM."""
    base_client, config = _get_client_and_config(db)
    system_prompt = (
        config.system_prompt
        .replace("{subject}", subject or "数学")
        .replace("{count}", str(count))
    )

    user_prompt = f"Source question: {source_text}\n"
    if grade:
        user_prompt += f"Grade: {grade}\n"
    if subject:
        user_prompt += f"Subject: {subject}\n"
    user_prompt += f"Return {count} variants."

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": config.temperature,
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
    prompt: Optional[str] = None,
    source_svg: Optional[str] = None,
    db: Optional[Session] = None,
) -> tuple[list[VariantItem], str]:
    """
    增强版举一反三：生成结构化的练习题（包含题目、答案、提示）。
    """
    base_client, config = _get_client_and_config(db)
    model = config.model
    temperature = config.temperature
    subject_name = subject or "数学"
    system_prompt = (
        config.system_prompt
        .replace("{subject}", subject_name)
        .replace("{count}", str(count))
    )

    # 尝试读取 svg 内容（source_svg 可能是 URL 或内联 svg 字符串）
    source_svg_content: Optional[str] = None
    source_svg_bytes: Optional[bytes] = None
    if source_svg:
        raw = source_svg.strip()
        if raw.startswith("<svg") or raw.startswith("<?xml"):
            source_svg_content = raw
            source_svg_bytes = raw.encode("utf-8")
        elif raw.startswith("http") or raw.startswith("/static/"):
            fetched = get_storage_service().read_asset_bytes(raw)
            if fetched:
                source_svg_content = fetched.decode("utf-8", errors="replace")
                source_svg_bytes = fetched
                logger.info("variant_service: loaded source svg bytes=%d from url=%s", len(fetched), raw[:80])
            else:
                logger.warning("variant_service: could not load source svg from url=%s", raw[:80])

    normalized_prompt = (prompt or "").strip()
    user_prompt = f"原题：{source_text}\n"
    if source_svg_content:
        # 截取前 800 字符嵌入 prompt，让 LLM 了解图示结构
        svg_snippet = source_svg_content[:800]
        user_prompt += f"原题图示（SVG）：\n{svg_snippet}\n（生成的练习题需要配套类似风格的图示）\n"
    elif source_svg:
        user_prompt += "（原题附有图示，生成的练习题也需要配图）\n"
    if grade:
        user_prompt += f"年级：{grade}\n"
    user_prompt += f"请出{count}道类似的练习题。"
    if normalized_prompt:
        user_prompt += f"\n\n{CUSTOM_PROMPT_PREFIX}\n{normalized_prompt}"

    used_prompt = f"[system]\n{system_prompt}\n\n[user]\n{user_prompt}"
    logger.info(
        "Variants prompt resolved subject=%s count=%s custom_prompt=%r used_prompt=%r",
        subject_name,
        count,
        normalized_prompt or None,
        used_prompt,
    )

    try:
        items = _request_variant_items(
            base_client=base_client,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_id="variant_generate_for_question",
            count=count,
        )
    except LlmClientError as exc:
        logger.exception("generate_variants_for_question LLM request failed")
        raise RuntimeError(f"LLM request failed: {str(exc)}") from exc

    used_prompt_parts = [used_prompt]
    attempts = 0
    while len(items) < count and attempts < 2:
        attempts += 1
        remaining = count - len(items)
        existing_texts = "\n".join(f"- {item.text}" for item in items if item.text.strip())
        retry_system_prompt = (
            config.system_prompt
            .replace("{subject}", subject_name)
            .replace("{count}", str(remaining))
        )
        retry_user_prompt = (
            f"原题：{source_text}\n"
            f"已经生成了{len(items)}道题，但还缺{remaining}道。\n"
            f"请只补充剩余的{remaining}道，不要重复已有题目。\n"
        )
        if grade:
            retry_user_prompt += f"年级：{grade}\n"
        if existing_texts:
            retry_user_prompt += f"已有题目：\n{existing_texts}\n"
        if normalized_prompt:
            retry_user_prompt += f"\n{CUSTOM_PROMPT_PREFIX}\n{normalized_prompt}\n"
        retry_used_prompt = f"[system]\n{retry_system_prompt}\n\n[user]\n{retry_user_prompt}"
        used_prompt_parts.append(retry_used_prompt)
        logger.info(
            "Variants underfilled count=%s current=%s retry=%s prompt=%r",
            count,
            len(items),
            attempts,
            retry_used_prompt,
        )
        try:
            retry_items = _request_variant_items(
                base_client=base_client,
                model=model,
                temperature=temperature,
                system_prompt=retry_system_prompt,
                user_prompt=retry_user_prompt,
                trace_id=f"variant_generate_for_question_retry_{attempts}",
                count=remaining,
            )
        except LlmClientError as exc:
            logger.exception("generate_variants_for_question retry failed")
            raise RuntimeError(f"LLM request failed: {str(exc)}") from exc

        existing_text_set = {item.text.strip() for item in items if item.text.strip()}
        for retry_item in retry_items:
            normalized_text = retry_item.text.strip()
            if not normalized_text or normalized_text in existing_text_set:
                continue
            items.append(retry_item)
            existing_text_set.add(normalized_text)
            if len(items) >= count:
                break

    final_items = items[:count]

    # 如果原题有 svg，为每道变式生成 svg（svg 内容已嵌入 prompt，不需要传 bytes）
    if source_svg_content:
        for idx, item in enumerate(final_items):
            try:
                svg = generate_diagram_svg(
                    item.text,
                    trace_id=f"variant_svg_{idx}",
                    db=db,
                )
                item.svg = svg
            except Exception as exc:
                logger.warning("Failed to generate svg for variant %d: %s", idx, exc)

    return final_items, "\n\n--- retry ---\n\n".join(used_prompt_parts)
