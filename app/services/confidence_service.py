from __future__ import annotations

from typing import Any, Optional


def _option_count(rebuild_json: Optional[dict[str, Any]]) -> int:
    if not rebuild_json:
        return 0
    options = rebuild_json.get("options")
    if isinstance(options, list):
        return sum(1 for value in options if isinstance(value, str) and value.strip())
    return 0


def compute_rebuild_assessment(
    *,
    source_text: str,
    rebuild_json: Optional[dict[str, Any]],
    has_image: bool,
    has_diagram_output: bool,
    clean_fallback_used: bool,
) -> dict[str, Any]:
    score = 0.0
    reasons: list[str] = []
    breakdown: dict[str, float] = {
        "text_signal": 0.0,
        "structure_signal": 0.0,
        "diagram_signal": 0.0,
        "fallback_penalty": 0.0,
    }

    text_len = len((source_text or "").strip())
    if text_len >= 8:
        breakdown["text_signal"] += 0.22
        reasons.append("text_len_good")
    elif text_len >= 3:
        breakdown["text_signal"] += 0.12
        reasons.append("text_len_medium")
    else:
        reasons.append("text_len_short")

    if rebuild_json:
        breakdown["structure_signal"] += 0.33
        stem = rebuild_json.get("stem")
        if isinstance(stem, str) and len(stem.strip()) >= 5:
            breakdown["structure_signal"] += 0.12
            reasons.append("stem_valid")
        else:
            reasons.append("stem_weak")
        if _option_count(rebuild_json) >= 2:
            breakdown["structure_signal"] += 0.12
            reasons.append("options_rich")
        if rebuild_json.get("source") == "llm":
            breakdown["structure_signal"] += 0.09
            reasons.append("llm_rebuild")
        else:
            reasons.append("heuristic_rebuild")
    else:
        reasons.append("rebuild_missing")

    if has_image:
        if has_diagram_output:
            breakdown["diagram_signal"] += 0.10
            reasons.append("diagram_present")
        else:
            breakdown["diagram_signal"] -= 0.15
            reasons.append("diagram_missing_for_image_question")

    if clean_fallback_used:
        breakdown["fallback_penalty"] -= 0.05
        reasons.append("saas_fallback_used")

    score = sum(breakdown.values())
    score = max(0.0, min(1.0, score))
    return {
        "score": round(score, 3),
        "reasons": reasons,
        "breakdown": {k: round(v, 3) for k, v in breakdown.items()},
    }


def compute_rebuild_confidence(
    *,
    source_text: str,
    rebuild_json: Optional[dict[str, Any]],
    has_image: bool,
    has_diagram_output: bool,
    clean_fallback_used: bool,
) -> float:
    assessment = compute_rebuild_assessment(
        source_text=source_text,
        rebuild_json=rebuild_json,
        has_image=has_image,
        has_diagram_output=has_diagram_output,
        clean_fallback_used=clean_fallback_used,
    )
    return float(assessment["score"])
