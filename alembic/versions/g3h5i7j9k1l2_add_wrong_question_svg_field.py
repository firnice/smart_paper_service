"""add wrong question svg field

Revision ID: g3h5i7j9k1l2
Revises: f2a1c9d8e7b6
Create Date: 2026-04-06 23:50:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "g3h5i7j9k1l2"
down_revision = "f2a1c9d8e7b6"
branch_labels = None
depends_on = None


def _get_existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing_columns = _get_existing_columns("wrong_questions")
    if "svg" not in existing_columns:
        op.add_column("wrong_questions", sa.Column("svg", sa.Text(), nullable=True))
    if "image_name" in existing_columns:
        op.drop_column("wrong_questions", "image_name")
    if "original_image_name" in existing_columns:
        op.drop_column("wrong_questions", "original_image_name")


def downgrade() -> None:
    existing_columns = _get_existing_columns("wrong_questions")
    if "svg" in existing_columns:
        op.drop_column("wrong_questions", "svg")
    if "image_name" not in existing_columns:
        op.add_column("wrong_questions", sa.Column("image_name", sa.String(255), nullable=True))
    if "original_image_name" not in existing_columns:
        op.add_column("wrong_questions", sa.Column("original_image_name", sa.String(255), nullable=True))
