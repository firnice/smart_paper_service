"""add trend_analyses table

Revision ID: b4c6d8e0f2a4
Revises: a3b5c7d9e1f3
Create Date: 2026-03-27 10:00:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b4c6d8e0f2a4'
down_revision = 'a3b5c7d9e1f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'trend_analyses',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.Integer(), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', index=True),
        sa.Column('start_date', sa.String(10), nullable=True),
        sa.Column('end_date', sa.String(10), nullable=True),
        sa.Column('subject_filter', sa.String(64), nullable=True),
        sa.Column('input_snapshot', sa.Text(), nullable=True),
        sa.Column('analysis_result', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('trend_analyses')
