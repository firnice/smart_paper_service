"""backfill builtin model providers

Revision ID: m8n0p2q4r6s8
Revises: k7l9m1n3o5p7
Create Date: 2026-04-07 16:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "m8n0p2q4r6s8"
down_revision = "k7l9m1n3o5p7"
branch_labels = None
depends_on = None

DEFAULT_PROVIDERS = (
    {"name": "siliconflow", "base_url": "https://api.siliconflow.cn/v1"},
    {"name": "whatai", "base_url": "https://api.whatai.cc/v1"},
)


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("model_providers"):
        return

    conn = op.get_bind()

    # Step 1: 去重（保留每个 name 中 id 最小的行，删除其余重复行）
    conn.execute(sa.text(
        """
        DELETE FROM model_providers
        WHERE id NOT IN (
            SELECT MIN(id) FROM model_providers GROUP BY name
        )
        """
    ))

    # Step 2: 建唯一索引（去重后再建，避免冲突）
    if not _has_index("model_providers", "ix_model_providers_name"):
        op.create_index("ix_model_providers_name", "model_providers", ["name"], unique=True)

    # Step 3: 补充缺失的内置供应商（空 key，等运行时从 secrets 填充）
    for provider in DEFAULT_PROVIDERS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM model_providers WHERE name = :name LIMIT 1"),
            {"name": provider["name"]},
        ).scalar()
        if exists:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO model_providers (name, base_url, api_key, is_active, created_at, updated_at)
                VALUES (:name, :base_url, '', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            provider,
        )


def downgrade() -> None:
    if _has_table("model_providers") and _has_index("model_providers", "ix_model_providers_name"):
        op.drop_index("ix_model_providers_name", table_name="model_providers")
