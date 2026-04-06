#!/usr/bin/env python3
"""Export API regression checks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes.export import create_print_pack_export  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import Export  # noqa: E402
from app.schemas.export import ExportResponse, PrintPackExportRequest  # noqa: E402


def test_print_pack_export_persists_record_and_returns_numeric_id() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    captured: dict[str, object] = {}

    def fake_create_print_pack_export(**kwargs):
        captured.update(kwargs)
        return ExportResponse(
            job_id="print-pack-job-001",
            status="completed",
            download_url="/static/exports/print-pack-job-001.pdf",
        )

    with patch("app.api.routes.export.export_service.create_print_pack_export", side_effect=fake_create_print_pack_export):
        db = TestingSessionLocal()
        try:
            payload = create_print_pack_export(
                payload=PrintPackExportRequest(
                    student_id=5,
                    title="智能错题本·打印重做包-2026-04-06",
                    answer_mode="sheet",
                    paper_meta={
                        "student_name": "张三",
                        "class_name": "三年级二班",
                        "date": "2026-04-06",
                    },
                    items=[
                        {
                            "id": "orig-123",
                            "source_question_id": 123,
                            "type": "orig",
                            "order": 1,
                            "text": "原题内容",
                            "answer": "原题答案",
                            "image_url": "/static/q123.png",
                        },
                        {
                            "id": "var_001",
                            "source_question_id": 123,
                            "type": "ai",
                            "order": 2,
                            "text": "变式题内容",
                            "answer": "变式题答案",
                            "image_url": None,
                        },
                    ],
                ),
                db=db,
            ).model_dump()
        finally:
            db.close()

    assert payload["id"] == 1
    assert payload["status"] == "completed"
    assert payload["download_url"] == "/static/exports/print-pack-job-001.pdf"
    assert captured["answer_mode"] == "sheet"
    assert len(captured["items"]) == 2

    db = TestingSessionLocal()
    try:
        export_record = db.query(Export).filter(Export.job_id == "print-pack-job-001").first()
        assert export_record is not None
        assert export_record.status == "completed"
        assert export_record.download_url == "/static/exports/print-pack-job-001.pdf"
    finally:
        db.close()
