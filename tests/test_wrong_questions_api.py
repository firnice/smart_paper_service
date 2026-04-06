#!/usr/bin/env python3
"""Wrong-question API regression checks."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes.wrong_questions import (  # noqa: E402
    create_wrong_question,
    get_wrong_question,
    list_wrong_questions,
)
from app.db.base import Base  # noqa: E402
from app.db.models import StudentProfile, User  # noqa: E402
from app.schemas.wrong_questions import WrongQuestionCreate  # noqa: E402


def test_wrong_question_original_image_fields_round_trip() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        student = User(name="Student A", role="student", status="active")
        db.add(student)
        db.flush()
        student_id = student.id
        db.add(StudentProfile(user_id=student.id, grade="三年级"))
        db.commit()
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        payload = {
            "student_id": student_id,
            "content": "1. 2+3=?",
            "grade": "三年级",
            "reference_answer": "2 + 3 = 5",
            "analysis": "直接计算加法即可。",
            "image_url": "http://example.com/question.png",
            "image_name": "question.png",
            "original_image_url": "http://example.com/original-paper.png",
            "original_image_name": "original-paper.png",
        }

        created = create_wrong_question(payload=WrongQuestionCreate(**payload), db=db).model_dump()
        assert created["image_url"] == payload["image_url"]
        assert created["image_name"] == payload["image_name"]
        assert created["reference_answer"] == payload["reference_answer"]
        assert created["analysis"] == payload["analysis"]
        assert created["original_image_url"] == payload["original_image_url"]
        assert created["original_image_name"] == payload["original_image_name"]

        detail = get_wrong_question(created["id"], db=db).model_dump()
        assert detail["reference_answer"] == payload["reference_answer"]
        assert detail["analysis"] == payload["analysis"]
        assert detail["original_image_url"] == payload["original_image_url"]
        assert detail["original_image_name"] == payload["original_image_name"]

        items = list_wrong_questions(db=db).model_dump()["items"]
        assert len(items) == 1
        assert items[0]["reference_answer"] == payload["reference_answer"]
        assert items[0]["analysis"] == payload["analysis"]
        assert items[0]["original_image_url"] == payload["original_image_url"]
        assert items[0]["original_image_name"] == payload["original_image_name"]
    finally:
        db.close()
