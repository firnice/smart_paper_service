#!/usr/bin/env python3
"""Variants API regression checks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes.variants import generate_variants_for_question  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import StudentProfile, Subject, User, WrongQuestion  # noqa: E402
from app.schemas.variants import VariantsForQuestionRequest  # noqa: E402
from app.services.variant_service import VariantItem  # noqa: E402


def test_generate_for_question_returns_used_prompt_and_placeholder_images() -> None:
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
        db.add(StudentProfile(user_id=student.id, grade="三年级"))
        subject = Subject(code="math", name="数学")
        db.add(subject)
        db.flush()
        wrong_question = WrongQuestion(
            student_id=student.id,
            content="把一条绳子剪成9段，每段长9米，这条绳子一共有多长？",
            grade="三年级下",
            subject_id=subject.id,
            image_url="/static/questions/q999_91_demo.svg",
            original_image_url="/static/questions/q999_original.png",
            reference_answer="9 × 9 = 81（米）",
            analysis="总长度等于段数乘每段长度。",
        )
        db.add(wrong_question)
        db.commit()
        wrong_question_id = wrong_question.id
    finally:
        db.close()

    captured: dict[str, object] = {}

    def fake_generate_variants_for_question(**kwargs):
        captured.update(kwargs)
        return (
            [
                VariantItem(text="一根彩带平均剪成8段，每段长7米，一共长多少米？", answer="56米", hint="段数乘长度"),
                VariantItem(text="一卷电线分成6段，每段长9米，这卷电线共长多少米？", answer="54米", hint="先数段数"),
            ],
            "[system]\n系统要求\n\n[user]\n补充要求",
        )

    with patch("app.api.routes.variants.variant_service.generate_variants_for_question", side_effect=fake_generate_variants_for_question):
        db = TestingSessionLocal()
        try:
            payload = generate_variants_for_question(
                payload=VariantsForQuestionRequest(
                    wrong_question_id=wrong_question_id,
                    count=2,
                    prompt="围绕同一知识点出2道题",
                    include_images=True,
                ),
                db=db,
            ).model_dump()
        finally:
            db.close()

    assert payload["source_question_id"] == wrong_question_id
    assert payload["used_prompt"] == "[system]\n系统要求\n\n[user]\n补充要求"
    assert payload["source_question"]["image_url"] == "/static/questions/q999_91_demo.svg"
    assert payload["source_question"]["original_image_url"] == "/static/questions/q999_original.png"
    assert payload["source_question"]["reference_answer"] == "9 × 9 = 81（米）"
    assert payload["items"][0]["id"] == "var_001"
    assert payload["items"][0]["image_url"] is None
    assert payload["items"][1]["id"] == "var_002"
    assert payload["items"][1]["image_url"] is None
    assert captured["prompt"] == "围绕同一知识点出2道题"
    assert captured["count"] == 2
    assert captured["subject"] == "数学"
