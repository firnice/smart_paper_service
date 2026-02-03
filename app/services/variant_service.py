import json
import re
from typing import Optional
from urllib import error, request

from app.core.llm_settings import load_llm_settings


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
    settings = load_llm_settings()
    if not settings or not settings.model:
        raise RuntimeError("SILICONFLOW config missing. Please set SILICONFLOW_MODEL.")

    user_prompt = f"Source question: {source_text}\n"
    if grade:
        user_prompt += f"Grade: {grade}\n"
    if subject:
        user_prompt += f"Subject: {subject}\n"
    user_prompt += f"Return {count} variants."

    payload = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }

    data = json.dumps(payload).encode("utf-8")
    api_url = f"{settings.base_url}/chat/completions"
    req = request.Request(
        api_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=settings.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"LLM request failed ({exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    variants = _parse_variants(content, count)
    if not variants and content.strip():
        return [content.strip()]
    return variants
