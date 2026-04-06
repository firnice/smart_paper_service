"""add school terms

Revision ID: h4i6j8k0l2m4
Revises: g3h5i7j9k1l2
Create Date: 2026-04-06 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "h4i6j8k0l2m4"
down_revision = "g3h5i7j9k1l2"
branch_labels = None
depends_on = None

GRADES = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"]
SEED_ROWS = []
for i, grade in enumerate(GRADES):
    for j, semester in enumerate(["上", "下"]):
        SEED_ROWS.append({
            "id": i * 2 + j + 1,
            "name": f"{grade}{semester}",
            "grade": grade,
            "semester": semester,
            "sort_order": i * 2 + j + 1,
        })


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # 1. Create school_terms table
    if not _has_table("school_terms"):
        op.create_table(
            "school_terms",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(20), nullable=False),
            sa.Column("grade", sa.String(20), nullable=False),
            sa.Column("semester", sa.String(4), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_school_terms_grade", "school_terms", ["grade"])
        op.create_index("ix_school_terms_sort_order", "school_terms", ["sort_order"])

    # 2. Seed 12 rows (INSERT OR IGNORE so it's idempotent)
    bind = op.get_bind()
    existing = bind.execute(sa.text("SELECT COUNT(*) FROM school_terms")).scalar()
    if existing == 0:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO school_terms (id, name, grade, semester, sort_order) "
                "VALUES (:id, :name, :grade, :semester, :sort_order)"
            ),
            SEED_ROWS,
        )

    # 3. Add current_term_id to student_profiles (SQLite: no FK constraint in ADD COLUMN)
    if not _has_column("student_profiles", "current_term_id"):
        op.add_column(
            "student_profiles",
            sa.Column("current_term_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_student_profiles_current_term_id", "student_profiles", ["current_term_id"])

    # 4. Add term_id to wrong_questions
    if not _has_column("wrong_questions", "term_id"):
        op.add_column(
            "wrong_questions",
            sa.Column("term_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_wrong_questions_term_id", "wrong_questions", ["term_id"])

        # 5. Backfill term_id from first_error_date + grade (SQLite-compatible subquery)
        op.execute("""
            UPDATE wrong_questions
            SET term_id = (
                SELECT st.id
                FROM school_terms st
                WHERE st.grade = wrong_questions.grade
                  AND st.semester = CASE
                    WHEN CAST(strftime('%m', wrong_questions.first_error_date) AS INTEGER)
                         IN (9, 10, 11, 12, 1) THEN '上'
                    ELSE '下'
                  END
                LIMIT 1
            )
            WHERE wrong_questions.first_error_date IS NOT NULL
        """)

    # 6. Add student_id and term_id to exports
    if not _has_column("exports", "student_id"):
        op.add_column(
            "exports",
            sa.Column("student_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_exports_student_id", "exports", ["student_id"])

    if not _has_column("exports", "term_id"):
        op.add_column(
            "exports",
            sa.Column("term_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_exports_term_id", "exports", ["term_id"])


def downgrade() -> None:
    if _has_column("exports", "term_id"):
        op.drop_index("ix_exports_term_id", table_name="exports")
        op.drop_column("exports", "term_id")
    if _has_column("exports", "student_id"):
        op.drop_index("ix_exports_student_id", table_name="exports")
        op.drop_column("exports", "student_id")
    if _has_column("wrong_questions", "term_id"):
        op.drop_index("ix_wrong_questions_term_id", table_name="wrong_questions")
        op.drop_column("wrong_questions", "term_id")
    if _has_column("student_profiles", "current_term_id"):
        op.drop_index("ix_student_profiles_current_term_id", table_name="student_profiles")
        op.drop_column("student_profiles", "current_term_id")
    if _has_table("school_terms"):
        op.drop_index("ix_school_terms_sort_order", table_name="school_terms")
        op.drop_index("ix_school_terms_grade", table_name="school_terms")
        op.drop_table("school_terms")
