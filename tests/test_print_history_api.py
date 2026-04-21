#!/usr/bin/env python3
"""print-pack export wiring: history rows + filename in response."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes.export import create_print_pack_export  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402
    SchoolTerm,
    StudentProfile,
    Subject,
    User,
    WrongQuestion,
    WrongQuestionPrintHistory,
)
from app.schemas.export import ExportResponse, PrintPackExportRequest  # noqa: E402


def _setup_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session


def _seed(db):
    subject = Subject(code="math", name="数学")
    db.add(subject)
    db.flush()
    term = SchoolTerm(name="三年级上", grade="三年级", semester="上", sort_order=5)
    db.add(term)
    db.flush()
    user = User(name="李明", role="student")
    db.add(user)
    db.flush()
    profile = StudentProfile(user_id=user.id, grade="三年级", current_term_id=term.id)
    db.add(profile)
    db.flush()
    wq = WrongQuestion(
        student_id=user.id,
        grade="三年级",
        content="1+1=?",
        subject_id=subject.id,
    )
    db.add(wq)
    db.flush()
    return user.id, wq.id


def _payload(student_id: int, wrong_question_id: int) -> PrintPackExportRequest:
    return PrintPackExportRequest(
        student_id=student_id,
        title="T",
        answer_mode="hidden",
        paper_meta={"student_name": "李明", "class_name": "三(2)班", "date": "2026-04-20"},
        items=[
            {
                "id": "orig-1",
                "source_question_id": wrong_question_id,
                "type": "orig",
                "order": 1,
                "text": "Q",
                "answer": "",
                "image_url": None,
            },
            {
                "id": "ai-1",
                "source_question_id": wrong_question_id,
                "type": "ai",
                "order": 2,
                "text": "V",
                "answer": "",
                "image_url": None,
            },
        ],
    )


def test_success_writes_one_history_row_per_unique_source_and_returns_filename():
    Session = _setup_db()
    db = Session()
    try:
        sid, wq_id = _seed(db)
        db.commit()

        def fake_svc(**kwargs):
            return ExportResponse(
                job_id="job-x1",
                status="completed",
                download_url="/static/exports/job-x1.pdf",
            )

        with patch(
            "app.api.routes.export.export_service.create_print_pack_export",
            side_effect=fake_svc,
        ), patch(
            "app.services.print_filename_service.datetime"
        ) as mdt:
            mdt.now.return_value = datetime(2026, 4, 20, 14, 35)
            response = create_print_pack_export(payload=_payload(sid, wq_id), db=db).model_dump()

        assert response["status"] == "completed"
        assert response["filename"] == "李-三年级-上-数学-20260420-1435.pdf"

        rows = db.query(WrongQuestionPrintHistory).all()
        assert len(rows) == 1
        assert rows[0].wrong_question_id == wq_id
        assert rows[0].student_id == sid
    finally:
        db.close()


def test_failed_export_writes_no_history_rows_and_no_filename():
    Session = _setup_db()
    db = Session()
    try:
        sid, wq_id = _seed(db)
        db.commit()

        def fake_svc(**kwargs):
            return ExportResponse(job_id="job-x2", status="failed", download_url=None)

        with patch(
            "app.api.routes.export.export_service.create_print_pack_export",
            side_effect=fake_svc,
        ):
            response = create_print_pack_export(payload=_payload(sid, wq_id), db=db).model_dump()

        assert response["status"] == "failed"
        assert response["filename"] is None
        assert db.query(WrongQuestionPrintHistory).count() == 0
    finally:
        db.close()


def test_history_dedupes_per_source_question_and_skips_null_ids():
    Session = _setup_db()
    db = Session()
    try:
        sid, wq_id = _seed(db)
        subject2 = db.query(Subject).first()
        wq2 = WrongQuestion(
            student_id=sid,
            grade="三年级",
            content="other",
            subject_id=subject2.id,
        )
        db.add(wq2)
        db.flush()
        db.commit()

        payload = PrintPackExportRequest(
            student_id=sid,
            title="T",
            answer_mode="hidden",
            paper_meta={"student_name": "李明", "date": "2026-04-20"},
            items=[
                {"id": "orig-1", "source_question_id": wq_id, "type": "orig", "order": 1, "text": "Q1"},
                {"id": "orig-2", "source_question_id": wq_id, "type": "orig", "order": 2, "text": "Q1-dup"},
                {"id": "orig-3", "source_question_id": wq2.id, "type": "orig", "order": 3, "text": "Q2"},
                {"id": "ai-standalone", "source_question_id": None, "type": "ai", "order": 4, "text": "V"},
            ],
        )

        def fake_svc(**kwargs):
            return ExportResponse(
                job_id="job-x3", status="completed", download_url="/x.pdf"
            )

        with patch(
            "app.api.routes.export.export_service.create_print_pack_export",
            side_effect=fake_svc,
        ):
            create_print_pack_export(payload=payload, db=db)

        rows = db.query(WrongQuestionPrintHistory).all()
        wq_ids_in_history = {r.wrong_question_id for r in rows}
        assert wq_ids_in_history == {wq_id, wq2.id}
        assert len(rows) == 2
    finally:
        db.close()
