#!/usr/bin/env python3
"""Wrong-question API regression checks."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes.wrong_questions import router as wrong_questions_router  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import StudentProfile, User  # noqa: E402
from app.db.session import get_db  # noqa: E402


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(wrong_questions_router)
    return test_app


def test_wrong_question_original_image_fields_round_trip() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = _build_test_app()
    app.dependency_overrides[get_db] = override_get_db

    try:
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

        with TestClient(app) as client:
            payload = {
                "student_id": student_id,
                "content": "1. 2+3=?",
                "grade": "三年级",
                "image_url": "http://example.com/question.png",
                "image_name": "question.png",
                "original_image_url": "http://example.com/original-paper.png",
                "original_image_name": "original-paper.png",
            }

            create_response = client.post("/api/wrong-questions", json=payload)
            assert create_response.status_code == 201
            created = create_response.json()
            assert created["image_url"] == payload["image_url"]
            assert created["image_name"] == payload["image_name"]
            assert created["original_image_url"] == payload["original_image_url"]
            assert created["original_image_name"] == payload["original_image_name"]

            detail_response = client.get(f"/api/wrong-questions/{created['id']}")
            assert detail_response.status_code == 200
            detail = detail_response.json()
            assert detail["original_image_url"] == payload["original_image_url"]
            assert detail["original_image_name"] == payload["original_image_name"]

            list_response = client.get("/api/wrong-questions")
            assert list_response.status_code == 200
            items = list_response.json()["items"]
            assert len(items) == 1
            assert items[0]["original_image_url"] == payload["original_image_url"]
            assert items[0]["original_image_name"] == payload["original_image_name"]
    finally:
        app.dependency_overrides.pop(get_db, None)
