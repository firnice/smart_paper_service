# 打印历史记录 + 打印包文件命名 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在打印流程中记录每道错题的历史打印次数，使下次进入打印页时默认不再勾选这些题；同时把导出 PDF 的文件名改为 `{姓}-{年级}-{学期}-{学科}-{YYYYMMDD-HHMM}.pdf` 可读格式。

**Architecture:** 新建 `wrong_question_print_history` 关联表记录每次 print-pack 导出对应的错题；改造 `POST /api/print-pack/export` 在同一事务内写入历史并返回计算好的 `filename`；扩展 `GET /api/wrong-questions` 通过 LEFT JOIN 子查询聚合 `print_count` 和 `last_printed_at`；前端 `PrintPage` 调整默认勾选规则并在选题列表展示徽章。

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / Alembic / SQLite (test) / pytest；前端 React / Vite / Tailwind / Sonner toast。

**Spec:** `docs/superpowers/specs/2026-04-20-print-history-and-filename-design.md`

---

## File Structure

### 新建
- `app/db/models/wrong_question_print_history.py` — 新 ORM 模型（单一职责：记录一次打印的一道错题）
- `alembic/versions/<rev>_add_wrong_question_print_history.py` — 建表迁移
- `app/services/print_filename_service.py` — 纯函数 `build_print_pack_filename(db, student_id, source_question_ids, now)`，与 PDF 生成解耦
- `tests/test_print_filename_service.py` — 命名拼接单元测试
- `tests/test_print_history_api.py` — print_pack 导出写入 history + list 接口聚合字段的集成测试

### 修改
- `app/db/models/__init__.py` — 注册新模型（确保 Alembic autogen 能看到；以及导入项目约定）
- `app/db/models/wrong_question.py` — 反向关系 `print_history`（便于级联删除和测试断言）
- `app/db/models/export.py` — 反向关系 `print_history`
- `app/db/models/user.py` — 反向关系 `print_history`（按学生过滤用）
- `app/schemas/export.py` — `PrintPackExportResponse` 增加 `filename: Optional[str]`
- `app/schemas/wrong_questions.py` — `WrongQuestionResponse` 增加 `print_count: int`、`last_printed_at: Optional[datetime]`
- `app/services/export_service.py` — `create_print_pack_export` 内部新增钩子：同事务写入 history + 计算 filename；签名需能接收 `db: Session`
- `app/api/routes/export.py` — 在路由中串联 db 事务：exports 记录 + history 写入 + filename 生成 + 响应返回
- `app/api/routes/wrong_questions.py` — `list_wrong_questions` 里 LEFT JOIN 聚合子查询；`_serialize_wrong_question` 接收 print_count/last_printed_at 参数
- `smart_paper_web/src/pages/print/helpers.js` — `mapWrongQuestionToPrintQuestion` 新增字段；加 `formatShortDate`
- `smart_paper_web/src/pages/PrintPage.jsx` — `resolveInitialSelection` 排除已打印
- `smart_paper_web/src/pages/print/components/SelectQuestionsStep.jsx` — 三视图加徽章
- `smart_paper_web/src/pages/PrintPage.jsx` `handleExport` — toast 显示 filename

### 不改
- `app/api/routes/export.py` 的 `POST /api/export`（旧版接口）
- 其它页面（QuestionBank/QuestionDetail 等）

---

## Task 1: 新增 `wrong_question_print_history` ORM 模型

**Files:**
- Create: `app/db/models/wrong_question_print_history.py`
- Modify: `app/db/models/__init__.py`
- Modify: `app/db/models/wrong_question.py`
- Modify: `app/db/models/export.py`
- Modify: `app/db/models/user.py`
- Test: `tests/test_print_history_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_print_history_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_print_history_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'WrongQuestionPrintHistory'`

- [ ] **Step 3: Create the model file**

Create `app/db/models/wrong_question_print_history.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class WrongQuestionPrintHistory(Base):
    """记录每次打印包导出时涉及的错题，用于避免重复默认勾选"""

    __tablename__ = "wrong_question_print_history"

    id = Column(Integer, primary_key=True, index=True)
    wrong_question_id = Column(
        Integer,
        ForeignKey("wrong_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_id = Column(
        Integer,
        ForeignKey("exports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    printed_at = Column(DateTime, nullable=False, index=True, default=func.now())

    wrong_question = relationship("WrongQuestion", back_populates="print_history")
    export = relationship("Export", back_populates="print_history")
    student = relationship("User", back_populates="print_history")
```

- [ ] **Step 4: Register the model in `app/db/models/__init__.py`**

Modify `app/db/models/__init__.py` to append the new model import and `__all__` entry:

```python
from app.db.models.wrong_question_print_history import WrongQuestionPrintHistory
```

And add `"WrongQuestionPrintHistory"` to `__all__`.

- [ ] **Step 5: Add back-populates on related models**

Modify `app/db/models/wrong_question.py` — inside the `WrongQuestion` class's `# Relationships` block, append:

```python
    print_history = relationship(
        "WrongQuestionPrintHistory",
        back_populates="wrong_question",
        cascade="all, delete-orphan",
    )
```

Modify `app/db/models/export.py` — append to the class:

```python
    print_history = relationship(
        "WrongQuestionPrintHistory",
        back_populates="export",
        cascade="all, delete-orphan",
    )
```

Modify `app/db/models/user.py` — append inside the User relationships block:

```python
    print_history = relationship(
        "WrongQuestionPrintHistory",
        back_populates="student",
        foreign_keys="WrongQuestionPrintHistory.student_id",
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_print_history_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add app/db/models/wrong_question_print_history.py app/db/models/__init__.py app/db/models/wrong_question.py app/db/models/export.py app/db/models/user.py tests/test_print_history_model.py
git commit -m "feat(db): add WrongQuestionPrintHistory model

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Alembic migration for `wrong_question_print_history`

**Files:**
- Create: `alembic/versions/<generated>_add_wrong_question_print_history.py`
- Test: `tests/test_print_history_migration.py` (smoke)

- [ ] **Step 1: Inspect current head revision**

Run: `alembic heads`
Expected: prints the current head revision id (e.g. `1e0f3c7b2a11` or later). Note this id as `<CURRENT_HEAD>` for the next step.

- [ ] **Step 2: Generate migration skeleton**

Run: `alembic revision -m "add wrong question print history"`
Expected: creates a new file `alembic/versions/<rev>_add_wrong_question_print_history.py` with `revision = '<rev>'` and `down_revision = '<CURRENT_HEAD>'`.

- [ ] **Step 3: Fill in the upgrade/downgrade**

Open the generated file and replace the `upgrade()`/`downgrade()` bodies:

```python
def upgrade() -> None:
    op.create_table(
        "wrong_question_print_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "wrong_question_id",
            sa.Integer(),
            sa.ForeignKey("wrong_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "export_id",
            sa.Integer(),
            sa.ForeignKey("exports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "printed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_wqph_wrong_question_id",
        "wrong_question_print_history",
        ["wrong_question_id"],
    )
    op.create_index(
        "ix_wqph_export_id",
        "wrong_question_print_history",
        ["export_id"],
    )
    op.create_index(
        "ix_wqph_student_printed",
        "wrong_question_print_history",
        ["student_id", "printed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wqph_student_printed",
        table_name="wrong_question_print_history",
    )
    op.drop_index(
        "ix_wqph_export_id",
        table_name="wrong_question_print_history",
    )
    op.drop_index(
        "ix_wqph_wrong_question_id",
        table_name="wrong_question_print_history",
    )
    op.drop_table("wrong_question_print_history")
```

Keep the existing `revision = '...'` / `down_revision = '...'` / `branch_labels = None` / `depends_on = None` block as generated by Alembic.

- [ ] **Step 4: Run upgrade locally against the dev sqlite**

Run: `alembic upgrade head`
Expected: no errors. The sqlite file gains the new table.

- [ ] **Step 5: Add migration smoke test**

Create `tests/test_print_history_migration.py`:

```python
"""Smoke-check the model matches the migration schema."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base  # noqa: E402
from app.db.models import WrongQuestionPrintHistory  # noqa: E402


def test_table_indexes_exist():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    index_names = {idx["name"] for idx in inspector.get_indexes("wrong_question_print_history")}
    assert "ix_wqph_wrong_question_id" in index_names
    assert "ix_wqph_student_printed" in index_names
```

Note: the index names are declared via the Alembic migration; to mirror them in the ORM so `create_all` produces the same names, add this block to `app/db/models/wrong_question_print_history.py` at the end of the class:

```python
    __table_args__ = (
        # keep names in sync with the alembic migration
        __import__("sqlalchemy").Index(
            "ix_wqph_wrong_question_id", "wrong_question_id"
        ),
        __import__("sqlalchemy").Index(
            "ix_wqph_export_id", "export_id"
        ),
        __import__("sqlalchemy").Index(
            "ix_wqph_student_printed", "student_id", "printed_at"
        ),
    )
```

(Prefer a clean `from sqlalchemy import Index` at the top of the file; adjust the imports accordingly and drop the `__import__` trick.)

- [ ] **Step 6: Run smoke test**

Run: `pytest tests/test_print_history_migration.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/*add_wrong_question_print_history.py app/db/models/wrong_question_print_history.py tests/test_print_history_migration.py
git commit -m "feat(db): migrate wrong_question_print_history table

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: `build_print_pack_filename` service (pure function)

**Files:**
- Create: `app/services/print_filename_service.py`
- Test: `tests/test_print_filename_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_print_filename_service.py`:

```python
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
        # subject ids: subject_b was inserted first so has smaller id; check ascending order
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_print_filename_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.print_filename_service'`

- [ ] **Step 3: Implement the service**

Create `app/services/print_filename_service.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.db.models import StudentProfile, Subject, User, WrongQuestion


def _derive_surname(name: Optional[str]) -> str:
    if not name:
        return "学生"
    stripped = name.strip()
    if not stripped:
        return "学生"
    first_word = stripped.split()[0]
    if not first_word:
        return "学生"
    return first_word[0]


def _load_student_grade_and_semester(db: Session, student_id: Optional[int]) -> tuple[str, str]:
    if student_id is None:
        return "", ""
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == student_id)
        .one_or_none()
    )
    if profile is None:
        return "", ""
    if profile.current_term is not None:
        return (
            profile.current_term.grade or "",
            profile.current_term.semester or "",
        )
    return (profile.grade or "", "")


def _load_subjects_label(db: Session, source_question_ids: Sequence[int]) -> str:
    ids = [sid for sid in source_question_ids if sid is not None]
    if not ids:
        return "未分类"
    rows = (
        db.query(Subject.id, Subject.name)
        .join(WrongQuestion, WrongQuestion.subject_id == Subject.id)
        .filter(WrongQuestion.id.in_(ids))
        .distinct()
        .order_by(Subject.id.asc())
        .all()
    )
    names = [name for _, name in rows if name]
    if not names:
        return "未分类"
    return "_".join(names)


def _load_student_name(db: Session, student_id: Optional[int]) -> Optional[str]:
    if student_id is None:
        return None
    user = db.query(User).filter(User.id == student_id).one_or_none()
    return user.name if user else None


def build_print_pack_filename(
    db: Session,
    student_id: Optional[int],
    source_question_ids: Sequence[int],
    now: Optional[datetime] = None,
) -> str:
    """拼接打印包 PDF 文件名。

    规则：{姓}-{年级}-{学期}-{学科}-{YYYYMMDD-HHMM}.pdf
    空段（年级/学期）会被省略，避免出现双连字符。
    """
    now = now or datetime.now()
    surname = _derive_surname(_load_student_name(db, student_id))
    grade, semester = _load_student_grade_and_semester(db, student_id)
    subjects = _load_subjects_label(db, source_question_ids)
    time_str = now.strftime("%Y%m%d-%H%M")

    segments = [surname, grade, semester, subjects, time_str]
    segments = [seg for seg in segments if seg]
    return "-".join(segments) + ".pdf"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_print_filename_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/print_filename_service.py tests/test_print_filename_service.py
git commit -m "feat(export): add print-pack filename builder service

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Extend `PrintPackExportResponse` schema with `filename`

**Files:**
- Modify: `app/schemas/export.py`
- Test: `tests/test_export_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_export_schema.py`:

```python
"""Schema regression for PrintPackExportResponse.filename."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.export import PrintPackExportResponse  # noqa: E402


def test_filename_field_is_optional_string():
    # filename present
    r1 = PrintPackExportResponse(id=1, status="completed", download_url="/x.pdf", filename="李-三年级-上-数学-20260420-1435.pdf")
    assert r1.filename == "李-三年级-上-数学-20260420-1435.pdf"
    # filename absent defaults to None
    r2 = PrintPackExportResponse(id=2, status="failed")
    assert r2.filename is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_schema.py -v`
Expected: FAIL with `pydantic.ValidationError` or `TypeError: unexpected keyword 'filename'`

- [ ] **Step 3: Modify the schema**

Edit `app/schemas/export.py`, find the `PrintPackExportResponse` class and replace it with:

```python
class PrintPackExportResponse(BaseModel):
    id: int
    status: str
    download_url: Optional[str] = None
    filename: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/export.py tests/test_export_schema.py
git commit -m "feat(schema): add filename to PrintPackExportResponse

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Write `print_history` + `filename` inside `create_print_pack_export` route

**Files:**
- Modify: `app/api/routes/export.py`
- Test: `tests/test_print_history_api.py`

Key design: the existing `export_service.create_print_pack_export` remains pure (doesn't touch db). The **route** is the orchestrator: it calls the pure service to get the `ExportResponse`, then if `status == "completed"`, in the same `db` session it writes the `Export` record, the `WrongQuestionPrintHistory` rows, and computes `filename` via `print_filename_service.build_print_pack_filename`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_print_history_api.py`:

```python
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
    Export,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_print_history_api.py -v`
Expected: FAIL — the route does not yet write history or set `filename`.

- [ ] **Step 3: Modify the route to orchestrate history + filename**

Replace the body of `create_print_pack_export` in `app/api/routes/export.py` (the endpoint function, lines ~75-125) with:

```python
@router.post("/api/print-pack/export", response_model=PrintPackExportResponse)
def create_print_pack_export(payload: PrintPackExportRequest, db: Session = Depends(get_db), _: int = Depends(get_student_session)):
    response = export_service.create_print_pack_export(
        title=payload.title,
        paper_meta=payload.paper_meta,
        items=payload.items,
        answer_mode=payload.answer_mode,
    )

    # Resolve term from student profile
    resolved_term_id = None
    if payload.student_id:
        student = (
            db.query(User)
            .options(joinedload(User.student_profile).joinedload(StudentProfile.current_term))
            .filter(User.id == payload.student_id)
            .first()
        )
        if student and student.student_profile:
            resolved_term = term_service.get_effective_term(db, student.student_profile)
            resolved_term_id = resolved_term.id if resolved_term else None

    export_record = Export(
        job_id=response.job_id,
        title=payload.title,
        original_text="",
        variants_json=[item.model_dump() for item in payload.items],
        include_images=any(bool((item.image_url or "").strip()) for item in payload.items),
        format="pdf",
        status=response.status,
        download_url=response.download_url,
        error_message=None if response.status == "completed" else "Print-pack export failed",
        student_id=payload.student_id,
        term_id=resolved_term_id,
    )
    db.add(export_record)

    filename: Optional[str] = None
    if response.status == "completed":
        # Collect unique source_question_ids (non-null) for history + filename
        unique_ids: list[int] = []
        seen: set[int] = set()
        for item in payload.items:
            sid = item.source_question_id
            if sid is None or sid in seen:
                continue
            seen.add(sid)
            unique_ids.append(sid)

        try:
            db.flush()  # make export_record.id available
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist print-pack export record",
            ) from exc

        for source_id in unique_ids:
            db.add(
                WrongQuestionPrintHistory(
                    wrong_question_id=source_id,
                    export_id=export_record.id,
                    student_id=payload.student_id,
                    printed_at=export_record.created_at or datetime.utcnow(),
                )
            )

        filename = build_print_pack_filename(
            db=db,
            student_id=payload.student_id,
            source_question_ids=unique_ids,
        )

    try:
        db.commit()
        db.refresh(export_record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist print-pack export record",
        ) from exc

    return PrintPackExportResponse(
        id=export_record.id,
        status=response.status,
        download_url=response.download_url,
        filename=filename,
    )
```

Then update the imports at the top of `app/api/routes/export.py`:

```python
from datetime import datetime
from typing import Optional

from app.db.models import WrongQuestionPrintHistory
from app.services.print_filename_service import build_print_pack_filename
```

(Keep existing imports. The `Optional` import is for the new `filename` local variable type.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_print_history_api.py tests/test_export_api.py -v`
Expected: PASS for all tests (including the legacy `test_export_api.py` which should still pass because the fake service path works the same).

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/export.py tests/test_print_history_api.py
git commit -m "feat(export): write print_history and compute filename on print-pack export

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Aggregate `print_count` / `last_printed_at` in `GET /api/wrong-questions`

**Files:**
- Modify: `app/schemas/wrong_questions.py`
- Modify: `app/api/routes/wrong_questions.py`
- Test: `tests/test_wrong_questions_api.py` (add case)

- [ ] **Step 1: Extend the response schema**

Edit `app/schemas/wrong_questions.py`. In the `WrongQuestionResponse` class add two fields near the bottom (before `created_at`):

```python
    print_count: int = 0
    last_printed_at: Optional[datetime] = None
```

The `datetime` import already exists.

- [ ] **Step 2: Write the failing test**

Open `tests/test_wrong_questions_api.py` and add a new test (append to the end, keep existing tests unchanged):

```python
def test_list_returns_print_count_and_last_printed_at(tmp_path):
    """regression: list wrong-questions aggregates print history stats"""
    # NOTE: replace existing fixtures with the file's current style.
    # The test should:
    #   1. create a student + wrong_question
    #   2. create two Export records and two WrongQuestionPrintHistory rows
    #      with printed_at = (2026-04-10 10:00, 2026-04-15 09:00)
    #   3. call GET /api/wrong-questions as that student
    #   4. assert the list item's print_count == 2 and
    #      last_printed_at == '2026-04-15T09:00:00'
```

Because `tests/test_wrong_questions_api.py` may use a FastAPI test client or direct function calls, **read the existing test style first** (`Read` the top ~80 lines of the file). Port the fixtures/patterns that are already there — e.g. if other tests call `list_wrong_questions` as a function, do the same; if they use a `TestClient`, use the same. Replace the placeholder comment block with actual code that follows the existing style.

**Concrete implementation sketch (port to the file's actual style):**

```python
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.models import (
    Export, Subject, User, WrongQuestion, WrongQuestionPrintHistory,
)
from app.api.routes.wrong_questions import list_wrong_questions


def test_list_returns_print_count_and_last_printed_at():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        subject = Subject(code="math", name="数学"); db.add(subject); db.flush()
        user = User(name="张三", role="student"); db.add(user); db.flush()
        wq = WrongQuestion(student_id=user.id, grade="三年级", content="Q", subject_id=subject.id)
        db.add(wq); db.flush()
        e1 = Export(job_id="j1", title="t", original_text="", variants_json=[], status="completed")
        e2 = Export(job_id="j2", title="t", original_text="", variants_json=[], status="completed")
        db.add_all([e1, e2]); db.flush()
        db.add_all([
            WrongQuestionPrintHistory(wrong_question_id=wq.id, export_id=e1.id, student_id=user.id, printed_at=datetime(2026, 4, 10, 10, 0)),
            WrongQuestionPrintHistory(wrong_question_id=wq.id, export_id=e2.id, student_id=user.id, printed_at=datetime(2026, 4, 15, 9, 0)),
        ])
        db.commit()

        response = list_wrong_questions(
            student_id=user.id, subject_id=None, grade=None, status_value=None,
            category_id=None, error_reason_id=None, is_bookmarked=None,
            keyword=None, term_id=None, sort_by=None, sort_order=None,
            offset=0, limit=20, db=db, current_student_id=user.id,
        )

        items = response.items if hasattr(response, "items") else response["items"]
        assert len(items) == 1
        row = items[0]
        print_count = getattr(row, "print_count", None) or row["print_count"]
        last_printed_at = getattr(row, "last_printed_at", None) or row["last_printed_at"]
        assert print_count == 2
        assert last_printed_at == datetime(2026, 4, 15, 9, 0)
    finally:
        db.close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_wrong_questions_api.py::test_list_returns_print_count_and_last_printed_at -v`
Expected: FAIL — serializer doesn't include the new fields, or the query doesn't aggregate.

- [ ] **Step 4: Rewrite `list_wrong_questions` to aggregate in one SQL**

Edit `app/api/routes/wrong_questions.py`. Locate `list_wrong_questions` (around line 316) and its helper `_serialize_wrong_question` (around line 143). Apply **two** changes:

**4a. Extend `_serialize_wrong_question` signature to accept optional stats:**

```python
def _serialize_wrong_question(
    item: WrongQuestion,
    print_count: int = 0,
    last_printed_at: Optional[datetime] = None,
) -> WrongQuestionResponse:
```

Then in the returned `WrongQuestionResponse(...)` call, add two kwargs at the bottom:

```python
        print_count=print_count,
        last_printed_at=last_printed_at,
```

Add imports at the top of the file if not already present:

```python
from datetime import datetime
from typing import Optional
```

Also add the model import to the existing model import block:

```python
from app.db.models import WrongQuestionPrintHistory
```

**4b. Rewrite `list_wrong_questions` aggregation logic.** Find the block `total = query.count()` / `items = query.order_by(...)...all()` (around lines 386-391) and replace with:

```python
    from sqlalchemy import func, select

    resolved_sort_by = sort_by if sort_by in VALID_SORT_FIELDS else "updated_at"
    resolved_sort_order = sort_order if sort_order in VALID_SORT_ORDERS else "desc"
    sort_column = getattr(WrongQuestion, resolved_sort_by)
    order_expr = sort_column.asc() if resolved_sort_order == "asc" else sort_column.desc()

    total = query.count()

    stats_subq = (
        db.query(
            WrongQuestionPrintHistory.wrong_question_id.label("wq_id"),
            func.count(WrongQuestionPrintHistory.id).label("cnt"),
            func.max(WrongQuestionPrintHistory.printed_at).label("last_at"),
        )
        .filter(WrongQuestionPrintHistory.student_id == student_id)
        .group_by(WrongQuestionPrintHistory.wrong_question_id)
        .subquery()
    )

    rows = (
        query.add_columns(stats_subq.c.cnt, stats_subq.c.last_at)
        .outerjoin(stats_subq, stats_subq.c.wq_id == WrongQuestion.id)
        .order_by(order_expr)
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = []
    for row in rows:
        item, cnt, last_at = row
        serialized.append(
            _serialize_wrong_question(
                item,
                print_count=int(cnt or 0),
                last_printed_at=last_at,
            )
        )

    return WrongQuestionListResponse(total=total, items=serialized)
```

Delete the previous `items = query.order_by(order_expr).offset(offset).limit(limit).all()` and the old `return WrongQuestionListResponse(...)`.

Keep the existing `_resolve_sort`/`_validate_status` code before the aggregation block unchanged.

Also confirm the `_serialize_wrong_question(item)` call in `get_wrong_question` (around line 399) and `create_wrong_question` (around line 288) still works — they pass only one positional arg and `print_count`/`last_printed_at` default to 0/None. No edits needed there.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_wrong_questions_api.py -v`
Expected: all tests PASS (including the new one and the existing ones).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/wrong_questions.py app/api/routes/wrong_questions.py tests/test_wrong_questions_api.py
git commit -m "feat(wrong_questions): aggregate print_count and last_printed_at in list API

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Frontend — map new fields and add date helper

**Files:**
- Modify: `../smart_paper_web/src/pages/print/helpers.js`

- [ ] **Step 1: Add `formatShortDate` helper**

Edit `smart_paper_web/src/pages/print/helpers.js`. Near the other small helpers (top of the file, after `hashString`), add:

```js
export function formatShortDate(isoLike) {
  if (!isoLike) return "";
  const date = new Date(isoLike);
  if (Number.isNaN(date.getTime())) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}-${day}`;
}
```

- [ ] **Step 2: Extend `mapWrongQuestionToPrintQuestion`**

In the same file, find `mapWrongQuestionToPrintQuestion` and inside the returned object (after `imageName`) add:

```js
    printCount: item?.print_count || 0,
    lastPrintedAt: item?.last_printed_at || "",
    hasBeenPrinted: (item?.print_count || 0) > 0,
```

- [ ] **Step 3: Manual verification**

Run the dev server (or your usual frontend check) and confirm nothing errors out.

```bash
cd ../smart_paper_web && npm run lint  # or the project's lint script
```

Expected: clean (no new warnings).

- [ ] **Step 4: Commit**

```bash
cd ../smart_paper_web
git add src/pages/print/helpers.js
git commit -m "feat(print): map print_count/last_printed_at and add formatShortDate

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Frontend — exclude already-printed questions from default selection

**Files:**
- Modify: `../smart_paper_web/src/pages/PrintPage.jsx`

- [ ] **Step 1: Edit `resolveInitialSelection`**

Open `smart_paper_web/src/pages/PrintPage.jsx`. Replace the existing `resolveInitialSelection` function (lines 31-47) with:

```js
function resolveInitialSelection(items, requestedIds, previousIds) {
  const available = new Set(items.map((item) => item.id));

  if (requestedIds.length > 0) {
    return requestedIds.map(String).filter((id) => available.has(id));
  }

  if (previousIds.length > 0) {
    const kept = previousIds.filter((id) => available.has(id));
    if (kept.length > 0) return kept;
  }

  return items
    .filter((item) => item.status !== "mastered" && !item.hasBeenPrinted)
    .slice(0, 6)
    .map((item) => item.id);
}
```

- [ ] **Step 2: Verify in browser**

Run the dev server. Navigate to the print page after having already exported one batch. Confirm: a freshly-opened print page does NOT auto-check the question(s) that were in the last export. Manual selection still works.

- [ ] **Step 3: Commit**

```bash
cd ../smart_paper_web
git add src/pages/PrintPage.jsx
git commit -m "feat(print): skip already-printed questions in default selection

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Frontend — render the "已打印 N 次 · 最近 MM-DD" badge

**Files:**
- Modify: `../smart_paper_web/src/pages/print/components/SelectQuestionsStep.jsx`

- [ ] **Step 1: Import `formatShortDate`**

At the top of `SelectQuestionsStep.jsx` add:

```js
import { formatShortDate } from "../helpers.js";
```

- [ ] **Step 2: Add a shared badge component at the top of the file (after `renderMetaBadge`)**

```jsx
function PrintedBadge({ question }) {
  if (!question?.hasBeenPrinted) return null;
  const dateText = formatShortDate(question.lastPrintedAt);
  const suffix = dateText ? ` · 最近 ${dateText}` : "";
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
      <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
      已打印 {question.printCount} 次{suffix}
    </span>
  );
}
```

- [ ] **Step 3: Render the badge in the three card variants**

In `FullQuestionCard`, inside the meta row (the `<div className="mb-3 flex flex-wrap gap-2">...</div>` block), after the mastery badge, add:

```jsx
        <PrintedBadge question={question} />
```

Do the same in `CompactQuestionCard`'s meta row.

In `ListQuestionRow`, add the badge after the mastery badge span (inside the `hidden md:block` wrapper), wrapping in a fragment if needed. Concretely, replace the last `<div className="hidden md:block">` block with:

```jsx
      <div className="hidden md:block">
        <span className="inline-flex rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-medium text-rose-600">
          {question.mastery}
        </span>
      </div>
      <div className="hidden md:block">
        <PrintedBadge question={question} />
      </div>
```

Then update the grid template for the list row: find the line

```js
"grid items-center gap-3 px-3 py-3 grid-cols-[20px_72px_minmax(0,1fr)] md:grid-cols-[20px_92px_minmax(0,1fr)_112px_88px_96px]"
```

and extend the md grid to add a new column for the printed badge:

```js
"grid items-center gap-3 px-3 py-3 grid-cols-[20px_72px_minmax(0,1fr)] md:grid-cols-[20px_92px_minmax(0,1fr)_112px_88px_96px_140px]"
```

- [ ] **Step 4: Verify in browser**

Run the dev server. For a question that has `print_count > 0`, confirm the badge shows in Full, Compact, and List view modes.

- [ ] **Step 5: Commit**

```bash
cd ../smart_paper_web
git add src/pages/print/components/SelectQuestionsStep.jsx
git commit -m "feat(print): show printed badge with count + last date in select step

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Frontend — surface the new filename in the export toast

**Files:**
- Modify: `../smart_paper_web/src/pages/PrintPage.jsx`

- [ ] **Step 1: Edit `handleExport`**

Find `handleExport` (around lines 566-595). Locate the `toast.success("PDF 已生成");` line and replace it with:

```js
      toast.success(response?.filename ? `PDF 已生成：${response.filename}` : "PDF 已生成");
```

- [ ] **Step 2: Verify in browser**

Trigger an export. Observe the toast text contains the new filename pattern (`李-三年级-上-数学-20260420-1435.pdf`).

- [ ] **Step 3: Commit**

```bash
cd ../smart_paper_web
git add src/pages/PrintPage.jsx
git commit -m "feat(print): show generated filename in export toast

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: End-to-end smoke check

**Files:** none changed

- [ ] **Step 1: Full backend test suite**

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 2: Manual flow verification**

1. Start backend: `./start.sh` (or project equivalent)
2. Start frontend: `cd ../smart_paper_web && npm run dev`
3. Login as a student, create at least 2 wrong questions
4. Go to print page → select all → export. Confirm the toast contains filename `...-<subject>-YYYYMMDD-HHMM.pdf`.
5. Reload the print page. Confirm already-printed questions are **not** auto-checked and show the `已打印 1 次 · 最近 MM-DD` badge.
6. Re-export the remaining questions. Confirm prior questions now show `已打印 2 次`.

- [ ] **Step 3: Final commit (if any cleanup)**

If all passes with no additional code changes, skip. Otherwise commit any last fixups.

---

## Self-Review (already run by author)

- **Spec coverage:**
  - §2.1 needs 1 (history) + badge → Tasks 1, 2, 5, 6, 7, 9 ✔
  - §2.2 needs 2 (filename) → Tasks 3, 4, 5, 10 ✔
  - §3 non-functional (single-SQL aggregation) → Task 6 Step 4 uses one LEFT JOIN ✔
  - §4 data model → Tasks 1, 2 ✔
  - §5.1 same-transaction write + filename response → Task 5 ✔
  - §5.2 LEFT JOIN subquery aggregation → Task 6 ✔
  - §5.3 filename builder with all fallbacks → Task 3 ✔
  - §5.4 旧版 /api/export 不改 → not in plan scope (explicit non-goal) ✔
  - §6.1–6.5 frontend changes → Tasks 7–10 ✔
  - §7 testing strategy → unit + integration + manual ✔
  - §8 implementation order → plan order matches §8 ✔
- **Placeholder scan:** none (all code shown)
- **Type consistency:** `print_count: int`, `last_printed_at: Optional[datetime]` used consistently in schema + serializer + tests + frontend (`printCount`, `lastPrintedAt`, `hasBeenPrinted`)
