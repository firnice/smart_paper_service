"""add wrong question print history

Revision ID: 3943a36cd440
Revises: n9o1p3q5r7s9
Create Date: 2026-04-21 19:47:31.693363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3943a36cd440'
down_revision: Union[str, None] = 'n9o1p3q5r7s9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wrong_question_print_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "wrong_question_id",
            sa.Integer(),
            sa.ForeignKey("wrong_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "export_id",
            sa.Integer(),
            sa.ForeignKey("exports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "printed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_wqph_wrong_question_id",
        "wrong_question_print_history",
        ["wrong_question_id"],
    )
    op.create_index(
        "ix_wqph_export_id",
        "wrong_question_print_history",
        ["export_id"],
    )
    op.create_index(
        "ix_wqph_student_printed",
        "wrong_question_print_history",
        ["student_id", "printed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wqph_student_printed",
        table_name="wrong_question_print_history",
    )
    op.drop_index(
        "ix_wqph_export_id",
        table_name="wrong_question_print_history",
    )
    op.drop_index(
        "ix_wqph_wrong_question_id",
        table_name="wrong_question_print_history",
    )
    op.drop_table("wrong_question_print_history")
