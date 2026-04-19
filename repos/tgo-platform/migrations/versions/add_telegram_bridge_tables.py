"""Add Telegram bridge binding and outbox tables.

Revision ID: add_telegram_bridge_tables
Revises: add_telegram_topic_bindings
Create Date: 2026-04-19 21:22:26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "add_telegram_bridge_tables"
down_revision = "add_telegram_topic_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Compatibility cleanup for the previous mistaken bridge migration.
    op.execute("DROP TABLE IF EXISTS pt_telegram_topic_binding")

    op.create_table(
        "pt_telegram_bridge_binding",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_platform_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_platform_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_platform_type", sa.String(length=50), nullable=False),
        sa.Column("source_key", sa.String(length=512), nullable=False),
        sa.Column("source_from_uid", sa.String(length=255), nullable=False),
        sa.Column("source_display_name", sa.String(length=255), nullable=True),
        sa.Column("source_extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=255), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_platform_id"], ["pt_platforms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["telegram_platform_id"], ["pt_platforms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_platform_id", "source_key", name="uq_tg_bridge_binding_platform_source"),
    )
    op.create_index(op.f("ix_pt_telegram_bridge_binding_project_id"), "pt_telegram_bridge_binding", ["project_id"], unique=False)
    op.create_index(op.f("ix_pt_telegram_bridge_binding_source_platform_id"), "pt_telegram_bridge_binding", ["source_platform_id"], unique=False)
    op.create_index(op.f("ix_pt_telegram_bridge_binding_telegram_platform_id"), "pt_telegram_bridge_binding", ["telegram_platform_id"], unique=False)
    op.create_index(op.f("ix_pt_telegram_bridge_binding_topic_id"), "pt_telegram_bridge_binding", ["topic_id"], unique=False)
    op.create_index("ix_tg_bridge_binding_project_platform", "pt_telegram_bridge_binding", ["project_id", "telegram_platform_id"], unique=False)

    op.create_table(
        "pt_telegram_bridge_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_platform_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dedupe_key", sa.String(length=512), nullable=False),
        sa.Column("payload_text", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["binding_id"], ["pt_telegram_bridge_binding.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["telegram_platform_id"], ["pt_platforms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_platform_id", "dedupe_key", name="uq_tg_bridge_outbox_platform_dedupe"),
    )
    op.create_index(op.f("ix_pt_telegram_bridge_outbox_binding_id"), "pt_telegram_bridge_outbox", ["binding_id"], unique=False)
    op.create_index(op.f("ix_pt_telegram_bridge_outbox_telegram_platform_id"), "pt_telegram_bridge_outbox", ["telegram_platform_id"], unique=False)
    op.create_index("ix_tg_bridge_outbox_platform_status", "pt_telegram_bridge_outbox", ["telegram_platform_id", "status"], unique=False)
    op.create_index("ix_tg_bridge_outbox_status_fetched", "pt_telegram_bridge_outbox", ["status", "fetched_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tg_bridge_outbox_status_fetched", table_name="pt_telegram_bridge_outbox")
    op.drop_index("ix_tg_bridge_outbox_platform_status", table_name="pt_telegram_bridge_outbox")
    op.drop_index(op.f("ix_pt_telegram_bridge_outbox_telegram_platform_id"), table_name="pt_telegram_bridge_outbox")
    op.drop_index(op.f("ix_pt_telegram_bridge_outbox_binding_id"), table_name="pt_telegram_bridge_outbox")
    op.drop_table("pt_telegram_bridge_outbox")

    op.drop_index("ix_tg_bridge_binding_project_platform", table_name="pt_telegram_bridge_binding")
    op.drop_index(op.f("ix_pt_telegram_bridge_binding_topic_id"), table_name="pt_telegram_bridge_binding")
    op.drop_index(op.f("ix_pt_telegram_bridge_binding_telegram_platform_id"), table_name="pt_telegram_bridge_binding")
    op.drop_index(op.f("ix_pt_telegram_bridge_binding_source_platform_id"), table_name="pt_telegram_bridge_binding")
    op.drop_index(op.f("ix_pt_telegram_bridge_binding_project_id"), table_name="pt_telegram_bridge_binding")
    op.drop_table("pt_telegram_bridge_binding")
