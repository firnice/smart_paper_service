"""add agent_configs table

Revision ID: a3b5c7d9e1f3
Revises: 7c1d2f4a9e21
Create Date: 2026-03-26 20:00:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a3b5c7d9e1f3'
down_revision = '7c1d2f4a9e21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_configs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('node_name', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('display_name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('model', sa.String(128), nullable=False),
        sa.Column('base_url', sa.String(512), nullable=True),
        sa.Column('api_key_ref', sa.String(64), nullable=True),
        sa.Column('temperature', sa.Float(), server_default='0.2'),
        sa.Column('timeout_seconds', sa.Integer(), server_default='180'),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('user_prompt_template', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('agent_configs')
