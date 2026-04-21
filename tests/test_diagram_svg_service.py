from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes import ocr as ocr_route
from app.core.student_auth import create_student_token
from app.main import app
from app.services import diagram_llm_service
from app.services.agent_config_service import ResolvedAgentConfig
from app.services.llm_client_service import LlmHttpError


def _build_agent_config(*, model: str, fallback_models: list[str]) -> ResolvedAgentConfig:
    return ResolvedAgentConfig(
        node_name="diagram_svg",
        display_name="SVG 图表生成",
        description="",
        provider="whatai",
        model=model,
        fallback_models=fallback_models,
        base_url="https://example.com/v1",
        api_key="test-key",
        temperature=0.2,
        timeout_seconds=60,
        max_tokens=None,
        system_prompt="系统提示",
        user_prompt_template="题目：{question_text}",
        is_enabled=True,
        source="database",
    )


def test_generate_diagram_svg_uses_fallback_model_after_resource_exhausted(monkeypatch) -> None:
    attempted_models: list[str] = []
    config = _build_agent_config(
        model="gemini-3.1-pro-preview",
        fallback_models=["gemini-3.1-flash-image-preview"],
    )

    class _FakeClient:
        def chat_completions(self, payload, *, trace_id):
            attempted_models.append(payload["model"])
            if payload["model"] == "gemini-3.1-pro-preview":
                raise LlmHttpError(
                    status_code=500,
                    body='{"error":{"message":"Resource has been exhausted","status":"RESOURCE_EXHAUSTED"}}',
                )
            return {
                "choices": [
                    {
                        "message": {
                            "content": '<svg width="100" height="100"><rect x="1" y="1" width="98" height="98" fill="white" stroke="black"/></svg>'
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        diagram_llm_service,
        "get_llm_client_for_agent",
        lambda db, node_name: (_FakeClient(), config),
    )

    svg = diagram_llm_service.generate_diagram_svg(
        "测试题目",
        trace_id="diagram-svg:item:2",
        db=object(),
    )

    assert svg and svg.startswith("<svg")
    assert attempted_models == [
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-image-preview",
    ]


def test_generate_diagram_svg_includes_seed_image_bias_instruction(monkeypatch) -> None:
    captured_payloads: list[dict] = []
    config = _build_agent_config(
        model="gemini-3.1-pro-preview",
        fallback_models=[],
    )

    class _CaptureClient:
        def chat_completions(self, payload, *, trace_id):
            captured_payloads.append(payload)
            return {
                "choices": [
                    {
                        "message": {
                            "content": '<svg width="100" height="100"><circle cx="50" cy="50" r="40" fill="white" stroke="black"/></svg>'
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        diagram_llm_service,
        "get_llm_client_for_agent",
        lambda db, node_name: (_CaptureClient(), config),
    )

    svg = diagram_llm_service.generate_diagram_svg(
        "测试题目文字",
        trace_id="diagram-svg:item:3",
        reference_images=[(b"fake-image", "image/png")],
        db=object(),
    )

    assert svg and svg.startswith("<svg")
    assert len(captured_payloads) == 1
    user_content = captured_payloads[0]["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert "尽量模仿题目中的图例" in user_content[0]["text"]
    assert "不要把重点放在题目文字描述上" in user_content[0]["text"]
    assert user_content[1]["type"] == "image_url"


def test_generate_diagram_svg_includes_latest_svg_and_custom_prompt(monkeypatch) -> None:
    captured_payloads: list[dict] = []
    config = _build_agent_config(
        model="gemini-3.1-pro-preview",
        fallback_models=[],
    )

    class _CaptureClient:
        def chat_completions(self, payload, *, trace_id):
            captured_payloads.append(payload)
            return {
                "choices": [
                    {
                        "message": {
                            "content": '<svg width="100" height="100"><circle cx="50" cy="50" r="40" fill="white" stroke="black"/></svg>'
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        diagram_llm_service,
        "get_llm_client_for_agent",
        lambda db, node_name: (_CaptureClient(), config),
    )

    svg = diagram_llm_service.generate_diagram_svg(
        "测试题目文字",
        trace_id="diagram-svg:item:4",
        reference_images=[(b"fake-original-image", "image/jpeg")],
        latest_svg='<svg width="40" height="20"><rect x="1" y="1" width="38" height="18"/></svg>',
        custom_prompt="把下方括号改宽一点",
        db=object(),
    )

    assert svg and svg.startswith("<svg")
    assert len(captured_payloads) == 1
    user_content = captured_payloads[0]["messages"][1]["content"]
    assert "基于这版做增量修改" in user_content[0]["text"]
    assert "把下方括号改宽一点" in user_content[0]["text"]
    assert "<svg width=\"40\" height=\"20\">" in user_content[0]["text"]
    assert user_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_generate_diagram_svg_raises_explicit_error_when_all_models_fail(monkeypatch) -> None:
    config = _build_agent_config(
        model="gemini-3.1-pro-preview",
        fallback_models=["gemini-3.1-flash-image-preview"],
    )

    class _AlwaysFailClient:
        def chat_completions(self, payload, *, trace_id):
            raise LlmHttpError(
                status_code=500,
                body='{"error":{"message":"Resource has been exhausted","status":"RESOURCE_EXHAUSTED"}}',
            )

    monkeypatch.setattr(
        diagram_llm_service,
        "get_llm_client_for_agent",
        lambda db, node_name: (_AlwaysFailClient(), config),
    )

    with pytest.raises(diagram_llm_service.DiagramSvgUpstreamError) as exc_info:
        diagram_llm_service.generate_diagram_svg(
            "测试题目",
            trace_id="diagram-svg:item:2",
            db=object(),
        )

    assert "额度已耗尽" in str(exc_info.value)


def test_generate_diagram_svg_route_returns_502_for_upstream_error(monkeypatch) -> None:
    original_generate = ocr_route.diagram_llm_service.generate_diagram_svg

    def _raise_error(*args, **kwargs):
        raise diagram_llm_service.DiagramSvgUpstreamError("SVG 图示生成额度已耗尽，请稍后重试。")

    monkeypatch.setattr(ocr_route.diagram_llm_service, "generate_diagram_svg", _raise_error)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/ocr/diagram/svg",
                json={"question_text": "测试题目", "item_id": 2},
                headers={"x-student-token": create_student_token(1)},
            )
    finally:
        monkeypatch.setattr(ocr_route.diagram_llm_service, "generate_diagram_svg", original_generate)

    assert response.status_code == 502
    body = response.json()
    assert body["detail"] == "SVG 图示生成额度已耗尽，请稍后重试。"
    assert body.get("trace_id")


def test_generate_diagram_svg_route_requires_prompt_for_existing_svg(monkeypatch) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/ocr/diagram/svg",
            json={
                "question_text": "测试题目",
                "item_id": 2,
                "latest_svg": '<svg width="20" height="20"><rect x="1" y="1" width="18" height="18"/></svg>',
            },
            headers={"x-student-token": create_student_token(1)},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"] == "重新生成已有配图时必须提供 prompt。"


def test_generate_diagram_svg_route_passes_original_image_latest_svg_and_prompt(monkeypatch) -> None:
    original_generate = ocr_route.diagram_llm_service.generate_diagram_svg
    captured: dict = {}

    def _capture(question_text, **kwargs):
        captured["question_text"] = question_text
        captured.update(kwargs)
        return '<svg width="20" height="20"><rect x="1" y="1" width="18" height="18"/></svg>'

    monkeypatch.setattr(ocr_route.diagram_llm_service, "generate_diagram_svg", _capture)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/ocr/diagram/svg",
                json={
                    "question_text": "测试题目",
                    "item_id": 2,
                    "original_image_url": "data:image/png;base64,ZmFrZS1pbWFnZQ==",
                    "latest_svg": '<svg width="20" height="20"><rect x="1" y="1" width="18" height="18"/></svg>',
                    "prompt": "把右侧线段加长",
                },
                headers={"x-student-token": create_student_token(1)},
            )
    finally:
        monkeypatch.setattr(ocr_route.diagram_llm_service, "generate_diagram_svg", original_generate)

    assert response.status_code == 200
    assert captured["question_text"] == "测试题目"
    assert captured["custom_prompt"] == "把右侧线段加长"
    assert captured["latest_svg"].startswith("<svg")
    assert len(captured["reference_images"]) == 1
    assert captured["reference_images"][0][0] == b"fake-image"
    assert captured["reference_images"][0][1] == "image/png"
