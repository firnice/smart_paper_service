"""Schema regression for PrintPackExportResponse.filename."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.export import PrintPackExportResponse  # noqa: E402


def test_filename_field_is_optional_string():
    r1 = PrintPackExportResponse(
        id=1,
        status="completed",
        download_url="/x.pdf",
        filename="李-三年级-上-数学-20260420-1435.pdf",
    )
    assert r1.filename == "李-三年级-上-数学-20260420-1435.pdf"
    r2 = PrintPackExportResponse(id=2, status="failed")
    assert r2.filename is None
