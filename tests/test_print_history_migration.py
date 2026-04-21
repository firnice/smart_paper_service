"""Smoke-check the model matches the migration schema."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base  # noqa: E402
from app.db.models import WrongQuestionPrintHistory  # noqa: F401, E402


def test_table_indexes_exist():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    index_names = {idx["name"] for idx in inspector.get_indexes("wrong_question_print_history")}
    assert "ix_wqph_wrong_question_id" in index_names
    assert "ix_wqph_student_printed" in index_names
