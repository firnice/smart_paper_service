#!/usr/bin/env python3
"""Targeted checks for OCR pipeline M1/M2/M3 baseline."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes import ocr as ocr_route  # noqa: E402
from app.main import app  # noqa: E402
from app.core.ocr_extract_llm_config import load_ocr_extract_llm_config  # noqa: E402
from app.services import confidence_service, question_rebuild_service  # noqa: E402
from app.services import ocr_service  # noqa: E402
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


def test_custom_ocr_prompt_resolution() -> None:
    config = load_ocr_extract_llm_config()
    effective_prompt, used_prompt = ocr_service.resolve_extract_prompt(
        "  只保留印刷体题干，忽略老师批注。  "
    )
    assert used_prompt == "只保留印刷体题干，忽略老师批注。"
    assert config.user_prompt in effective_prompt
    assert "只保留印刷体题干，忽略老师批注。" in effective_prompt
    assert "请把它们合并成同一个 item" in effective_prompt

    default_prompt, empty_used_prompt = ocr_service.resolve_extract_prompt("   ")
    assert default_prompt == config.user_prompt
    assert empty_used_prompt is None


def test_extract_questions_returns_used_prompt() -> None:
    original_call = ocr_service._call_vision_completion
    captured: dict[str, str] = {}

    def _fake_call(**kwargs):
        captured["user_prompt"] = kwargs["user_prompt"]
        return (
            '[{"id":1,"text":"2+3=?","subject_tag":"加法","is_wrong":true,'
            '"wrong_reason":"把 2+3 算错了","correction_suggestion":"重新计算并核对答案"}]'
        )

    ocr_service._call_vision_completion = _fake_call
    try:
        items, used_prompt = ocr_service.extract_questions(
            b"fake-image",
            "image/png",
            "unit-test.png",
            prompt="按从上到下顺序输出",
        )
    finally:
        ocr_service._call_vision_completion = original_call

    assert len(items) == 1
    assert items[0].text == "1. 2+3=?"
    assert items[0].subject_tag == "加法"
    assert items[0].is_wrong is True
    assert items[0].wrong_reason == "把 2+3 算错了"
    assert items[0].correction_suggestion == "重新计算并核对答案"
    assert used_prompt == captured["user_prompt"]
    assert load_ocr_extract_llm_config().user_prompt in used_prompt
    assert "按从上到下顺序输出" in used_prompt


def test_extract_simple_route_returns_effective_prompt() -> None:
    original_extract_questions = ocr_service.extract_questions
    expected_prompt = "系统默认要求\n\n补充要求\n按从上到下顺序输出"

    def _fake_extract_questions(*args, **kwargs):
        return (
            [
                ocr_service.OcrItem(
                    id=1,
                    text="1. 2+3=?",
                    subject_tag="加法",
                    is_wrong=False,
                    wrong_reason=None,
                    correction_suggestion=None,
                    has_image=False,
                    question_box=None,
                    image_box=None,
                )
            ],
            expected_prompt,
        )

    original_preprocess = ocr_route.prepare_image_for_ocr_pipeline

    def _fake_preprocess(image_bytes, content_type, filename, enable_local_preprocess):
        return image_bytes, content_type, filename, {
            "preprocessing_enabled": False,
            "preprocessing_applied": False,
            "preprocessing_engine": None,
            "deskew_angle": None,
            "preprocessing_fallback_reason": None,
        }

    ocr_service.extract_questions = _fake_extract_questions
    ocr_route.prepare_image_for_ocr_pipeline = _fake_preprocess
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/ocr/extract/simple",
                files={"file": ("unit-test.png", b"fake-image", "image/png")},
                data={"prompt": "按从上到下顺序输出"},
            )
    finally:
        ocr_service.extract_questions = original_extract_questions
        ocr_route.prepare_image_for_ocr_pipeline = original_preprocess

    assert response.status_code == 200
    payload = response.json()
    assert payload["used_prompt"] == expected_prompt
    assert payload["prompt"] == expected_prompt


def test_extract_questions_uses_yaml_configured_model() -> None:
    original_get_client = ocr_service.get_siliconflow_client
    calls: list[dict[str, object]] = []

    class _FakeBaseClient:
        base_url = "https://example.com/v1"
        api_key = "test-key"
        timeout_seconds = 45

    class _FakeWrappedClient:
        base_client = _FakeBaseClient()

    class _FakeVisionClient:
        def __init__(self, *args, **kwargs):
            self.timeout_seconds = kwargs["timeout_seconds"]

        def chat_completions(self, payload, *, trace_id):
            calls.append({"model": payload["model"], "trace_id": trace_id})
            return {
                "choices": [
                    {
                        "message": {
                            "content": '[{"id":1,"text":"识别成功","subject_tag":"数学","is_wrong":false,"wrong_reason":null,"correction_suggestion":null}]'
                        }
                    }
                ]
            }

    ocr_service.get_siliconflow_client = lambda: _FakeWrappedClient()
    original_base_client = ocr_service.BaseLlmClient
    ocr_service.BaseLlmClient = _FakeVisionClient
    try:
        image = Image.new("RGB", (32, 32), color="white")
        image_bytes = _to_png_bytes(image)
        items, _used_prompt = ocr_service.extract_questions(
            image_bytes,
            "image/png",
            "yaml-model-test.png",
        )
    finally:
        ocr_service.get_siliconflow_client = original_get_client
        ocr_service.BaseLlmClient = original_base_client

    config = load_ocr_extract_llm_config()
    assert len(items) == 1
    assert items[0].text == "1. 识别成功"
    assert calls
    assert calls[0]["model"] == config.model
    assert str(calls[0]["trace_id"]).startswith("ocr_llm:yaml-model-test.png")


def main() -> int:
    tests = [
        ("annotation_rule_cleaning", test_annotation_rule_cleaning),
        ("rebuild_contract", test_rebuild_contract),
        ("shape_cutout_has_alpha", test_shape_cutout_has_alpha),
        ("confidence_assessment", test_confidence_assessment),
        ("custom_ocr_prompt_resolution", test_custom_ocr_prompt_resolution),
        ("extract_questions_returns_used_prompt", test_extract_questions_returns_used_prompt),
        ("extract_simple_route_returns_effective_prompt", test_extract_simple_route_returns_effective_prompt),
        ("extract_questions_uses_yaml_configured_model", test_extract_questions_uses_yaml_configured_model),
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
