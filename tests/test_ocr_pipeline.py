#!/usr/bin/env python3
"""Targeted checks for OCR pipeline M1/M2/M3 baseline."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import confidence_service, question_rebuild_service  # noqa: E402
from app.services.image_service import (  # noqa: E402
    clean_annotations_with_rules,
    crop_diagram_image_with_metadata,
    should_use_annotation_saas_fallback,
)


def _build_marked_diagram() -> Image.Image:
    image = Image.new("RGB", (360, 200), color="white")
    draw = ImageDraw.Draw(image)
    # Printed black lines (diagram-like)
    draw.line((30, 30, 330, 30), fill=(20, 20, 20), width=3)
    draw.line((30, 30, 30, 170), fill=(20, 20, 20), width=3)
    draw.rectangle((90, 70, 170, 140), outline=(0, 0, 0), width=2)
    # Red and blue annotations
    draw.line((40, 50, 320, 150), fill=(220, 40, 40), width=5)
    draw.line((320, 50, 60, 160), fill=(40, 80, 230), width=4)
    return image


def _to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_annotation_rule_cleaning() -> None:
    src = _build_marked_diagram()
    cleaned, stats = clean_annotations_with_rules(src)
    assert cleaned.size == src.size
    assert stats["original_mark_ratio"] > 0.0
    assert stats["removed_pixels"] >= 0
    should_fallback, reason = should_use_annotation_saas_fallback(stats)
    # This case should typically be handled locally.
    assert not (should_fallback and reason == "local_removed_too_little")


def test_rebuild_contract() -> None:
    payload = question_rebuild_service.rebuild_question_json("1. 2+2=?\nA.3\nB.4")
    assert "stem" in payload
    assert "options" in payload
    assert "sub_questions" in payload
    assert "diagram_required" in payload
    assert payload.get("source") in {"llm", "heuristic"}


def test_shape_cutout_has_alpha() -> None:
    src = _build_marked_diagram()
    src_bytes = _to_png_bytes(src)
    out_bytes, out_w, out_h, stats = crop_diagram_image_with_metadata(
        src_bytes,
        ymin=20,
        xmin=20,
        ymax=180,
        xmax=340,
        max_size=None,
    )
    assert out_w > 0 and out_h > 0
    assert "alpha_ratio" in stats

    with Image.open(BytesIO(out_bytes)) as out_img:
        assert "A" in out_img.getbands()
        alpha = out_img.getchannel("A")
        values = list(alpha.getdata())
        non_transparent = sum(1 for value in values if value > 0)
        total = max(1, out_img.width * out_img.height)
        ratio = non_transparent / total
        assert 0.01 <= ratio <= 0.95


def test_confidence_assessment() -> None:
    low = confidence_service.compute_rebuild_assessment(
        source_text="2+2?",
        rebuild_json=None,
        has_image=True,
        has_diagram_output=False,
        clean_fallback_used=True,
    )
    high = confidence_service.compute_rebuild_assessment(
        source_text="1. 已知正方形ABCD边长为4，求面积。",
        rebuild_json={
            "stem": "已知正方形ABCD边长为4，求面积。",
            "options": ["A. 8", "B. 16", "C. 12", "D. 4"],
            "sub_questions": [],
            "diagram_required": False,
            "source": "heuristic",
        },
        has_image=False,
        has_diagram_output=False,
        clean_fallback_used=False,
    )
    assert 0.0 <= float(low["score"]) <= 1.0
    assert 0.0 <= float(high["score"]) <= 1.0
    assert float(high["score"]) > float(low["score"])
    assert isinstance(low["reasons"], list)
    assert isinstance(high["breakdown"], dict)


def main() -> int:
    tests = [
        ("annotation_rule_cleaning", test_annotation_rule_cleaning),
        ("rebuild_contract", test_rebuild_contract),
        ("shape_cutout_has_alpha", test_shape_cutout_has_alpha),
        ("confidence_assessment", test_confidence_assessment),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
        except Exception as exc:  # pragma: no cover
            failed += 1
            print(f"[FAIL] {name}: {exc}")
    if failed:
        print(f"Failed: {failed}/{len(tests)}")
        return 1
    print(f"Passed: {len(tests)}/{len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
