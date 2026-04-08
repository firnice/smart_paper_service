"""add models field to model_providers

Revision ID: n9o1p3q5r7s9
Revises: m8n0p2q4r6s8
Create Date: 2026-04-07 18:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "n9o1p3q5r7s9"
down_revision = "m8n0p2q4r6s8"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("model_providers", "models"):
        op.add_column(
            "model_providers",
            sa.Column("models", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("model_providers", "models"):
        op.drop_column("model_providers", "models")
