import json
import re
from typing import Optional

from app.services.llm_client_service import LlmClientError, get_siliconflow_client


SYSTEM_PROMPT = (
    "You are a primary school math tutor. "
    "Generate variants with the same logic but different numbers or scenarios. "
    "Return ONLY a JSON array of strings."
)


def _parse_variants(text: str, count: int) -> list[str]:
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


def generate_variants(
    source_text: str,
    count: int = 3,
    grade: Optional[str] = None,
    subject: Optional[str] = None,
) -> list[str]:
    """Generate same-type variants via SiliconFlow."""
    client = get_siliconflow_client()
    if not client or not client.default_model:
        raise RuntimeError("SILICONFLOW config missing. Please set SILICONFLOW_MODEL.")

    user_prompt = f"Source question: {source_text}\n"
    if grade:
        user_prompt += f"Grade: {grade}\n"
    if subject:
        user_prompt += f"Subject: {subject}\n"
    user_prompt += f"Return {count} variants."

    payload = {
        "model": client.default_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }
    try:
        body = client.base_client.chat_completions(
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
