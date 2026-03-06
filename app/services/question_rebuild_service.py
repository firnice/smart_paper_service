from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any, Optional

from app.services.llm_client_service import (
    LlmClientError,
    get_siliconflow_client,
)

logger = logging.getLogger("uvicorn.error")

_OPTION_RE = re.compile(r"^\s*([A-D])[\.、\)]\s*(.+?)\s*$")
_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+[\.\、\)]\s*")

_SYSTEM_PROMPT = (
    "You are a worksheet structuring assistant. "
    "Return strict JSON only."
)

_USER_PROMPT_TEMPLATE = (
    "Convert the question text into JSON with keys: "
    "stem (string), options (array of strings), sub_questions (array of strings), "
    "diagram_required (boolean). "
    "If no options or sub-questions, return empty arrays. "
    "Question text:\\n{question_text}"
)


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return cleaned


def _parse_llm_json(text: str) -> Optional[dict[str, Any]]:
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
    stem = str(payload.get("stem", "")).strip()
    options = payload.get("options")
    sub_questions = payload.get("sub_questions")
    if not isinstance(options, list):
        options = []
    if not isinstance(sub_questions, list):
        sub_questions = []
    return {
        "stem": stem,
        "options": [str(value).strip() for value in options if str(value).strip()],
        "sub_questions": [str(value).strip() for value in sub_questions if str(value).strip()],
        "diagram_required": bool(payload.get("diagram_required", False)),
        "source": "llm",
    }


def _heuristic_rebuild(question_text: str, has_diagram: bool) -> dict[str, Any]:
    lines = [line.strip() for line in (question_text or "").splitlines() if line.strip()]
    options: list[str] = []
    stem_lines: list[str] = []
    sub_questions: list[str] = []

    for line in lines:
        option_match = _OPTION_RE.match(line)
        if option_match:
            options.append(f"{option_match.group(1)}. {option_match.group(2)}")
            continue
        if re.match(r"^\s*\(\d+\)", line):
            sub_questions.append(line)
            continue
        stem_lines.append(line)

    stem = " ".join(stem_lines).strip()
    stem = _NUMBER_PREFIX_RE.sub("", stem).strip()
    if not stem and lines:
        stem = _NUMBER_PREFIX_RE.sub("", lines[0]).strip()

    return {
        "stem": stem,
        "options": options,
        "sub_questions": sub_questions,
        "diagram_required": bool(has_diagram),
        "source": "heuristic",
    }


def _call_llm_rebuild(question_text: str, diagram_image_bytes: Optional[bytes]) -> Optional[dict[str, Any]]:
    client = get_siliconflow_client()
    if not client or not client.default_model:
        return None

    user_content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": _USER_PROMPT_TEMPLATE.format(question_text=question_text or ""),
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
        "model": client.default_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
    }

    try:
        data = client.base_client.chat_completions(
            payload,
            trace_id="rebuild_question_json",
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
            parsed = _parse_llm_json("\n".join(text_chunks))
        else:
            parsed = _parse_llm_json(str(content or ""))
        return parsed
    except (LlmClientError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Question rebuild LLM call failed: %s", str(exc))
        return None


def rebuild_question_json(
    question_text: str,
    *,
    diagram_image_bytes: Optional[bytes] = None,
) -> dict[str, Any]:
    llm_result = _call_llm_rebuild(question_text, diagram_image_bytes)
    if llm_result:
        return llm_result
    return _heuristic_rebuild(question_text, has_diagram=bool(diagram_image_bytes))
