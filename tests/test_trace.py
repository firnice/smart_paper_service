#!/usr/bin/env python3
"""Trace helper regression checks."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.trace import compose_trace_id, get_trace_id, reset_trace_id, set_trace_id  # noqa: E402
from app.main import _attach_trace_id_to_json_response  # noqa: E402


def test_compose_trace_id_includes_request_scope() -> None:
    token = set_trace_id("req-123")
    try:
        assert get_trace_id() == "req-123"
        assert compose_trace_id("variant-generate") == "req-123:variant-generate"
    finally:
        reset_trace_id(token)


def test_trace_id_injected_into_api_json_object_response() -> None:
    async def _run():
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/health",
                "headers": [],
                "query_string": b"",
            }
        )
        response = JSONResponse({"status": "ok"})
        enriched = await _attach_trace_id_to_json_response(request, response, "trace-abc")
        body = bytes(enriched.body or b"")
        payload = json.loads(body.decode("utf-8"))
        assert payload["trace_id"] == "trace-abc"
        assert payload["status"] == "ok"

    asyncio.run(_run())


def test_trace_id_does_not_wrap_json_list_response() -> None:
    async def _run():
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/demo-list",
                "headers": [],
                "query_string": b"",
            }
        )
        response = JSONResponse([{"id": 1}])
        enriched = await _attach_trace_id_to_json_response(request, response, "trace-abc")
        body = bytes(enriched.body or b"")
        payload = json.loads(body.decode("utf-8"))
        assert payload == [{"id": 1}]

    asyncio.run(_run())


def main() -> int:
    try:
        test_compose_trace_id_includes_request_scope()
        test_trace_id_injected_into_api_json_object_response()
        test_trace_id_does_not_wrap_json_list_response()
    except Exception as exc:  # pragma: no cover
        print(f"[FAIL] trace: {exc}")
        return 1

    print("[PASS] trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
