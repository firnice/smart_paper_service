#!/usr/bin/env python3
"""OpenAPI documentation smoke checks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.openapi import get_openapi_documentation_gaps  # noqa: E402
from app.main import app  # noqa: E402


def test_openapi_has_required_metadata() -> None:
    gaps = get_openapi_documentation_gaps(app)
    assert not gaps, "\n".join(gaps)


def main() -> int:
    try:
        test_openapi_has_required_metadata()
    except Exception as exc:  # pragma: no cover
        print(f"[FAIL] openapi_docs: {exc}")
        return 1

    print("[PASS] openapi_docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
