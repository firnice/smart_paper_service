"""add wrong question image fields

Revision ID: 1e0f3c7b2a11
Revises: 6a8f9c40d713
Create Date: 2026-03-17 16:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e0f3c7b2a11'
down_revision = '6a8f9c40d713'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('wrong_questions', sa.Column('image_url', sa.Text(), nullable=True))
    op.add_column('wrong_questions', sa.Column('image_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('wrong_questions', 'image_name')
    op.drop_column('wrong_questions', 'image_url')
