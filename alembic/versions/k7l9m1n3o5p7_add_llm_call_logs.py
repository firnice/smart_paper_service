"""add llm_call_logs table

Revision ID: k7l9m1n3o5p7
Revises: j6k8l0m2n4o6
Create Date: 2026-04-07 10:10:00
"""

import sqlalchemy as sa
from alembic import op

revision = "k7l9m1n3o5p7"
down_revision = "j6k8l0m2n4o6"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("llm_call_logs"):
        op.create_table(
            "llm_call_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("trace_id", sa.String(256), nullable=False),
            sa.Column("agent_node", sa.String(64), nullable=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("model", sa.String(128), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("elapsed_ms", sa.Integer(), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=True),
            sa.Column("output_tokens", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("called_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_llm_call_logs_id", "llm_call_logs", ["id"])
        op.create_index("ix_llm_call_logs_trace_id", "llm_call_logs", ["trace_id"])
        op.create_index("ix_llm_call_logs_agent_node", "llm_call_logs", ["agent_node"])
        op.create_index("ix_llm_call_logs_student_id", "llm_call_logs", ["student_id"])
        op.create_index("ix_llm_call_logs_status", "llm_call_logs", ["status"])
        op.create_index("ix_llm_call_logs_called_at", "llm_call_logs", ["called_at"])


def downgrade() -> None:
    if _has_table("llm_call_logs"):
        op.drop_index("ix_llm_call_logs_called_at", table_name="llm_call_logs")
        op.drop_index("ix_llm_call_logs_status", table_name="llm_call_logs")
        op.drop_index("ix_llm_call_logs_student_id", table_name="llm_call_logs")
        op.drop_index("ix_llm_call_logs_agent_node", table_name="llm_call_logs")
        op.drop_index("ix_llm_call_logs_trace_id", table_name="llm_call_logs")
        op.drop_index("ix_llm_call_logs_id", table_name="llm_call_logs")
        op.drop_table("llm_call_logs")
