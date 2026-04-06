"""add birth_date to student_profiles

Revision ID: i5j7k9l1m3n5
Revises: h4i6j8k0l2m4
Create Date: 2026-04-06 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "i5j7k9l1m3n5"
down_revision = "h4i6j8k0l2m4"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("student_profiles", "birth_date"):
        op.add_column(
            "student_profiles",
            sa.Column("birth_date", sa.String(7), nullable=True),  # "YYYY-MM"
        )


def downgrade() -> None:
    if _has_column("student_profiles", "birth_date"):
        op.drop_column("student_profiles", "birth_date")
