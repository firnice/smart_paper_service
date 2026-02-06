"""User and wrong-question management schema

Revision ID: 6a8f9c40d713
Revises: 9f08e21dd859
Create Date: 2026-02-06 09:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a8f9c40d713"
down_revision: Union[str, None] = "9f08e21dd859"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_status"), "users", ["status"], unique=False)

    op.create_table(
        "student_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("student_no", sa.String(length=64), nullable=True),
        sa.Column("grade", sa.String(length=20), nullable=False),
        sa.Column("class_name", sa.String(length=50), nullable=True),
        sa.Column("school_name", sa.String(length=255), nullable=True),
        sa.Column("guardian_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_student_profiles_grade"), "student_profiles", ["grade"], unique=False)
    op.create_index(op.f("ix_student_profiles_id"), "student_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_student_profiles_user_id"), "student_profiles", ["user_id"], unique=True)

    op.create_table(
        "parent_student_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_id", "student_id", name="uq_parent_student_link"),
    )
    op.create_index(
        op.f("ix_parent_student_links_id"),
        "parent_student_links",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parent_student_links_parent_id"),
        "parent_student_links",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parent_student_links_student_id"),
        "parent_student_links",
        ["student_id"],
        unique=False,
    )

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_subjects_code"), "subjects", ["code"], unique=True)
    op.create_index(op.f("ix_subjects_id"), "subjects", ["id"], unique=False)

    op.create_table(
        "wrong_question_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_wrong_question_categories_id"),
        "wrong_question_categories",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wrong_question_categories_name"),
        "wrong_question_categories",
        ["name"],
        unique=True,
    )

    op.create_table(
        "error_reasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["wrong_question_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "category_id", name="uq_error_reason_name_category"),
    )
    op.create_index(op.f("ix_error_reasons_category_id"), "error_reasons", ["category_id"], unique=False)
    op.create_index(op.f("ix_error_reasons_id"), "error_reasons", ["id"], unique=False)
    op.create_index(op.f("ix_error_reasons_name"), "error_reasons", ["name"], unique=False)

    op.create_table(
        "wrong_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("paper_id", sa.Integer(), nullable=True),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("grade", sa.String(length=20), nullable=False),
        sa.Column("question_type", sa.String(length=50), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("is_bookmarked", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("first_error_date", sa.Date(), nullable=True),
        sa.Column("last_review_date", sa.Date(), nullable=True),
        sa.Column("last_practice_result", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["wrong_question_categories.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wrong_questions_category_id"), "wrong_questions", ["category_id"], unique=False)
    op.create_index(
        op.f("ix_wrong_questions_created_by_user_id"),
        "wrong_questions",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_wrong_questions_grade"), "wrong_questions", ["grade"], unique=False)
    op.create_index(op.f("ix_wrong_questions_id"), "wrong_questions", ["id"], unique=False)
    op.create_index(op.f("ix_wrong_questions_paper_id"), "wrong_questions", ["paper_id"], unique=False)
    op.create_index(op.f("ix_wrong_questions_question_id"), "wrong_questions", ["question_id"], unique=False)
    op.create_index(op.f("ix_wrong_questions_status"), "wrong_questions", ["status"], unique=False)
    op.create_index(op.f("ix_wrong_questions_student_id"), "wrong_questions", ["student_id"], unique=False)
    op.create_index(op.f("ix_wrong_questions_subject_id"), "wrong_questions", ["subject_id"], unique=False)

    op.create_table(
        "wrong_question_error_reasons",
        sa.Column("wrong_question_id", sa.Integer(), nullable=False),
        sa.Column("error_reason_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["error_reason_id"],
            ["error_reasons.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wrong_question_id"],
            ["wrong_questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wrong_question_id", "error_reason_id"),
    )

    op.create_table(
        "study_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wrong_question_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("study_date", sa.Date(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
        sa.Column("mastery_level", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["wrong_question_id"], ["wrong_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_study_records_id"), "study_records", ["id"], unique=False)
    op.create_index(op.f("ix_study_records_reviewer_user_id"), "study_records", ["reviewer_user_id"], unique=False)
    op.create_index(op.f("ix_study_records_student_id"), "study_records", ["student_id"], unique=False)
    op.create_index(op.f("ix_study_records_study_date"), "study_records", ["study_date"], unique=False)
    op.create_index(op.f("ix_study_records_wrong_question_id"), "study_records", ["wrong_question_id"], unique=False)

    subject_table = sa.table(
        "subjects",
        sa.column("id", sa.Integer()),
        sa.column("code", sa.String(length=50)),
        sa.column("name", sa.String(length=100)),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        subject_table,
        [
            {"id": 1, "code": "math", "name": "数学", "is_active": True},
            {"id": 2, "code": "chinese", "name": "语文", "is_active": True},
            {"id": 3, "code": "english", "name": "英语", "is_active": True},
            {"id": 4, "code": "science", "name": "科学", "is_active": True},
        ],
    )

    category_table = sa.table(
        "wrong_question_categories",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String(length=100)),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        category_table,
        [
            {"id": 1, "name": "概念不清", "description": "基础概念理解偏差"},
            {"id": 2, "name": "计算失误", "description": "计算过程出错或粗心"},
            {"id": 3, "name": "审题错误", "description": "题目信息读取不完整"},
            {"id": 4, "name": "步骤缺失", "description": "关键步骤缺失导致结果错误"},
            {"id": 5, "name": "知识点混淆", "description": "相近知识点混用"},
        ],
    )

    reason_table = sa.table(
        "error_reasons",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String(length=100)),
        sa.column("description", sa.Text()),
        sa.column("category_id", sa.Integer()),
    )
    op.bulk_insert(
        reason_table,
        [
            {"id": 1, "name": "公式记忆错误", "description": "公式或法则记忆不准确", "category_id": 1},
            {"id": 2, "name": "概念边界不清", "description": "相近概念边界没有厘清", "category_id": 1},
            {"id": 3, "name": "进位借位出错", "description": "四则运算进位借位错误", "category_id": 2},
            {"id": 4, "name": "抄写数字错误", "description": "数字抄写或看错", "category_id": 2},
            {"id": 5, "name": "漏看条件", "description": "遗漏题目限定条件", "category_id": 3},
            {"id": 6, "name": "单位忽略", "description": "忽略单位或单位转换", "category_id": 3},
            {"id": 7, "name": "过程跳步", "description": "解题过程未完整展开", "category_id": 4},
            {"id": 8, "name": "校验缺失", "description": "没有做结果校验", "category_id": 4},
            {"id": 9, "name": "题型混淆", "description": "同类题型规则混用", "category_id": 5},
            {"id": 10, "name": "方法选择不当", "description": "解题方法与题型不匹配", "category_id": 5},
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_study_records_wrong_question_id"), table_name="study_records")
    op.drop_index(op.f("ix_study_records_study_date"), table_name="study_records")
    op.drop_index(op.f("ix_study_records_student_id"), table_name="study_records")
    op.drop_index(op.f("ix_study_records_reviewer_user_id"), table_name="study_records")
    op.drop_index(op.f("ix_study_records_id"), table_name="study_records")
    op.drop_table("study_records")

    op.drop_table("wrong_question_error_reasons")

    op.drop_index(op.f("ix_wrong_questions_subject_id"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_student_id"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_status"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_question_id"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_paper_id"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_id"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_grade"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_created_by_user_id"), table_name="wrong_questions")
    op.drop_index(op.f("ix_wrong_questions_category_id"), table_name="wrong_questions")
    op.drop_table("wrong_questions")

    op.drop_index(op.f("ix_error_reasons_name"), table_name="error_reasons")
    op.drop_index(op.f("ix_error_reasons_id"), table_name="error_reasons")
    op.drop_index(op.f("ix_error_reasons_category_id"), table_name="error_reasons")
    op.drop_table("error_reasons")

    op.drop_index(op.f("ix_wrong_question_categories_name"), table_name="wrong_question_categories")
    op.drop_index(op.f("ix_wrong_question_categories_id"), table_name="wrong_question_categories")
    op.drop_table("wrong_question_categories")

    op.drop_index(op.f("ix_subjects_id"), table_name="subjects")
    op.drop_index(op.f("ix_subjects_code"), table_name="subjects")
    op.drop_table("subjects")

    op.drop_index(op.f("ix_parent_student_links_student_id"), table_name="parent_student_links")
    op.drop_index(op.f("ix_parent_student_links_parent_id"), table_name="parent_student_links")
    op.drop_index(op.f("ix_parent_student_links_id"), table_name="parent_student_links")
    op.drop_table("parent_student_links")

    op.drop_index(op.f("ix_student_profiles_user_id"), table_name="student_profiles")
    op.drop_index(op.f("ix_student_profiles_id"), table_name="student_profiles")
    op.drop_index(op.f("ix_student_profiles_grade"), table_name="student_profiles")
    op.drop_table("student_profiles")

    op.drop_index(op.f("ix_users_status"), table_name="users")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
