"""add wrong question original image fields

Revision ID: c9d2e4f6a8b1
Revises: b4c6d8e0f2a4
Create Date: 2026-04-05 20:30:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c9d2e4f6a8b1"
down_revision = "b4c6d8e0f2a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wrong_questions", sa.Column("original_image_url", sa.Text(), nullable=True))
    op.add_column("wrong_questions", sa.Column("original_image_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("wrong_questions", "original_image_name")
    op.drop_column("wrong_questions", "original_image_url")
