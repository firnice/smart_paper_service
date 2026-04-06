"""add wrong question answer fields

Revision ID: f2a1c9d8e7b6
Revises: e4b7f9a1c2d3
Create Date: 2026-04-06 23:40:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f2a1c9d8e7b6"
down_revision = "e4b7f9a1c2d3"
branch_labels = None
depends_on = None


def _get_existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing_columns = _get_existing_columns("wrong_questions")
    if "reference_answer" not in existing_columns:
        op.add_column("wrong_questions", sa.Column("reference_answer", sa.Text(), nullable=True))
    if "analysis" not in existing_columns:
        op.add_column("wrong_questions", sa.Column("analysis", sa.Text(), nullable=True))


def downgrade() -> None:
    existing_columns = _get_existing_columns("wrong_questions")
    if "analysis" in existing_columns:
        op.drop_column("wrong_questions", "analysis")
    if "reference_answer" in existing_columns:
        op.drop_column("wrong_questions", "reference_answer")
