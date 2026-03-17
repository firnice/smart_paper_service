"""backfill metadata created_at

Revision ID: 7c1d2f4a9e21
Revises: 1e0f3c7b2a11
Create Date: 2026-03-17 23:55:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '7c1d2f4a9e21'
down_revision = '1e0f3c7b2a11'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE subjects SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE wrong_question_categories SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE error_reasons SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")


def downgrade() -> None:
    pass
