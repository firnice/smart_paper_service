#!/usr/bin/env python3
"""Wrong-question print history model regression checks."""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402
    Export,
    Subject,
    User,
    WrongQuestion,
    WrongQuestionPrintHistory,
)


def _make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def test_model_defines_expected_columns():
    engine = _make_engine()
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("wrong_question_print_history")}
    assert {
        "id",
        "wrong_question_id",
        "export_id",
        "student_id",
        "printed_at",
    }.issubset(columns)


def test_insert_and_relationships_work():
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        subject = Subject(code="math", name="数学")
        db.add(subject)
        db.flush()

        student = User(name="张三", role="student")
        db.add(student)
        db.flush()

        wq = WrongQuestion(
            student_id=student.id,
            grade="三年级",
            content="1+1=?",
            subject_id=subject.id,
        )
        db.add(wq)
        db.flush()

        export = Export(
            job_id="job-001",
            title="T",
            original_text="",
            variants_json=[],
            status="completed",
        )
        db.add(export)
        db.flush()

        record = WrongQuestionPrintHistory(
            wrong_question_id=wq.id,
            export_id=export.id,
            student_id=student.id,
            printed_at=datetime(2026, 4, 20, 14, 35),
        )
        db.add(record)
        db.commit()

        reloaded = db.query(WrongQuestionPrintHistory).first()
        assert reloaded.wrong_question_id == wq.id
        assert reloaded.export_id == export.id
        assert reloaded.student_id == student.id
        assert reloaded.printed_at == datetime(2026, 4, 20, 14, 35)
    finally:
        db.close()
