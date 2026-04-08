"""add model_providers table

Revision ID: j6k8l0m2n4o6
Revises: i5j7k9l1m3n5
Create Date: 2026-04-07 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "j6k8l0m2n4o6"
down_revision = "i5j7k9l1m3n5"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("model_providers"):
        op.create_table(
            "model_providers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("base_url", sa.String(512), nullable=False),
            sa.Column("api_key", sa.String(512), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_model_providers_id", "model_providers", ["id"])


def downgrade() -> None:
    if _has_table("model_providers"):
        op.drop_index("ix_model_providers_id", table_name="model_providers")
        op.drop_table("model_providers")
