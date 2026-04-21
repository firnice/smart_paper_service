#!/usr/bin/env python3
"""print filename builder unit tests."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402
    SchoolTerm,
    StudentProfile,
    Subject,
    User,
    WrongQuestion,
)
from app.services.print_filename_service import build_print_pack_filename  # noqa: E402


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _fixed_now():
    return datetime(2026, 4, 20, 14, 35)


def _seed_student(db, name: str, grade: str = "三年级", with_term: bool = True) -> int:
    user = User(name=name, role="student")
    db.add(user)
    db.flush()
    term_id = None
    if with_term:
        term = SchoolTerm(name="三年级上", grade="三年级", semester="上", sort_order=5)
        db.add(term)
        db.flush()
        term_id = term.id
    profile = StudentProfile(user_id=user.id, grade=grade, current_term_id=term_id)
    db.add(profile)
    db.flush()
    return user.id


def _seed_math_question(db, student_id: int) -> int:
    subject = Subject(code="math", name="数学")
    db.add(subject)
    db.flush()
    wq = WrongQuestion(
        student_id=student_id,
        grade="三年级",
        content="1+1=?",
        subject_id=subject.id,
    )
    db.add(wq)
    db.flush()
    return wq.id


def test_full_chinese_name_with_term_and_single_subject():
    db = _session()
    try:
        sid = _seed_student(db, "李明")
        wq_id = _seed_math_question(db, sid)
        result = build_print_pack_filename(db, sid, [wq_id], now=_fixed_now())
        assert result == "李-三年级-上-数学-20260420-1435.pdf"
    finally:
        db.close()


def test_english_name_first_word_first_char():
    db = _session()
    try:
        sid = _seed_student(db, "Li Ming")
        wq_id = _seed_math_question(db, sid)
        result = build_print_pack_filename(db, sid, [wq_id], now=_fixed_now())
        assert result == "L-三年级-上-数学-20260420-1435.pdf"
    finally:
        db.close()


def test_missing_student_id_uses_fallback_surname():
    db = _session()
    try:
        result = build_print_pack_filename(db, None, [], now=_fixed_now())
        assert result == "学生-未分类-20260420-1435.pdf"
    finally:
        db.close()


def test_no_current_term_falls_back_to_profile_grade():
    db = _session()
    try:
        sid = _seed_student(db, "王芳", grade="四年级", with_term=False)
        wq_id = _seed_math_question(db, sid)
        result = build_print_pack_filename(db, sid, [wq_id], now=_fixed_now())
        # semester segment empty -> dropped entirely
        assert result == "王-四年级-数学-20260420-1435.pdf"
    finally:
        db.close()


def test_multiple_subjects_sorted_by_id_and_joined_with_underscore():
    db = _session()
    try:
        sid = _seed_student(db, "赵六")
        subject_b = Subject(code="chinese", name="语文")
        subject_a = Subject(code="math", name="数学")
        db.add_all([subject_b, subject_a])
        db.flush()
        wq1 = WrongQuestion(student_id=sid, grade="三年级", content="a", subject_id=subject_b.id)
        wq2 = WrongQuestion(student_id=sid, grade="三年级", content="b", subject_id=subject_a.id)
        db.add_all([wq1, wq2])
        db.flush()
        result = build_print_pack_filename(db, sid, [wq1.id, wq2.id], now=_fixed_now())
        ids_sorted = sorted([subject_b.id, subject_a.id])
        name_by_id = {subject_b.id: "语文", subject_a.id: "数学"}
        expected_subjects = "_".join(name_by_id[i] for i in ids_sorted)
        assert result == f"赵-三年级-上-{expected_subjects}-20260420-1435.pdf"
    finally:
        db.close()


def test_all_null_subjects_render_as_unclassified():
    db = _session()
    try:
        sid = _seed_student(db, "孙七")
        wq = WrongQuestion(student_id=sid, grade="三年级", content="no-subject", subject_id=None)
        db.add(wq)
        db.flush()
        result = build_print_pack_filename(db, sid, [wq.id], now=_fixed_now())
        assert result == "孙-三年级-上-未分类-20260420-1435.pdf"
    finally:
        db.close()


def test_empty_source_ids_render_as_unclassified():
    db = _session()
    try:
        sid = _seed_student(db, "周九")
        result = build_print_pack_filename(db, sid, [], now=_fixed_now())
        assert result == "周-三年级-上-未分类-20260420-1435.pdf"
    finally:
        db.close()
