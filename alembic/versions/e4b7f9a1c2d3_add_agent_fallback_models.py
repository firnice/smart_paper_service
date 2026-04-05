"""add agent fallback models

Revision ID: e4b7f9a1c2d3
Revises: c9d2e4f6a8b1
Create Date: 2026-04-05 21:40:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e4b7f9a1c2d3"
down_revision = "c9d2e4f6a8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("fallback_models", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_configs", "fallback_models")
