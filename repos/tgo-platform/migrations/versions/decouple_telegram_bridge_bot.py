"""Decouple Telegram bridge bot from telegram platform records.

Revision ID: decouple_telegram_bridge_bot
Revises: add_telegram_bridge_tables
Create Date: 2026-04-19 23:59:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "decouple_telegram_bridge_bot"
down_revision = "add_telegram_bridge_tables"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _constraint_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {item["name"] for item in inspector.get_unique_constraints(table_name) if item.get("name")}


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {item["name"] for item in inspector.get_indexes(table_name) if item.get("name")}


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    if _has_table("pt_telegram_bridge_binding"):
        binding_columns = _column_names("pt_telegram_bridge_binding")
        if "telegram_platform_id" in binding_columns:
            op.alter_column(
                "pt_telegram_bridge_binding",
                "telegram_platform_id",
                existing_type=postgresql.UUID(as_uuid=True),
                nullable=True,
            )

        binding_constraints = _constraint_names("pt_telegram_bridge_binding")
        if "uq_tg_bridge_binding_project_source" not in binding_constraints:
            op.create_unique_constraint(
                "uq_tg_bridge_binding_project_source",
                "pt_telegram_bridge_binding",
                ["project_id", "source_key"],
            )
        if "uq_tg_bridge_binding_project_topic" not in binding_constraints:
            op.create_unique_constraint(
                "uq_tg_bridge_binding_project_topic",
                "pt_telegram_bridge_binding",
                ["project_id", "topic_id"],
            )

    if _has_table("pt_telegram_bridge_outbox"):
        outbox_columns = _column_names("pt_telegram_bridge_outbox")
        if "project_id" not in outbox_columns:
            op.add_column(
                "pt_telegram_bridge_outbox",
                sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            op.execute(
                sa.text(
                    """
                    UPDATE pt_telegram_bridge_outbox AS outbox
                    SET project_id = binding.project_id
                    FROM pt_telegram_bridge_binding AS binding
                    WHERE outbox.binding_id = binding.id
                    """
                )
            )
            op.alter_column(
                "pt_telegram_bridge_outbox",
                "project_id",
                existing_type=postgresql.UUID(as_uuid=True),
                nullable=False,
            )

        if "telegram_platform_id" in _column_names("pt_telegram_bridge_outbox"):
            op.alter_column(
                "pt_telegram_bridge_outbox",
                "telegram_platform_id",
                existing_type=postgresql.UUID(as_uuid=True),
                nullable=True,
            )

        outbox_constraints = _constraint_names("pt_telegram_bridge_outbox")
        if "uq_tg_bridge_outbox_project_dedupe" not in outbox_constraints:
            op.create_unique_constraint(
                "uq_tg_bridge_outbox_project_dedupe",
                "pt_telegram_bridge_outbox",
                ["project_id", "dedupe_key"],
            )

        outbox_indexes = _index_names("pt_telegram_bridge_outbox")
        if "ix_tg_bridge_outbox_project_status" not in outbox_indexes:
            op.create_index(
                "ix_tg_bridge_outbox_project_status",
                "pt_telegram_bridge_outbox",
                ["project_id", "status"],
                unique=False,
            )

    if not _has_table("pt_telegram_bridge_state"):
        op.create_table(
            "pt_telegram_bridge_state",
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("last_update_id", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("project_id"),
        )


def downgrade() -> None:
    if _has_table("pt_telegram_bridge_state"):
        op.drop_table("pt_telegram_bridge_state")

    if _has_table("pt_telegram_bridge_outbox"):
        outbox_indexes = _index_names("pt_telegram_bridge_outbox")
        if "ix_tg_bridge_outbox_project_status" in outbox_indexes:
            op.drop_index("ix_tg_bridge_outbox_project_status", table_name="pt_telegram_bridge_outbox")

        outbox_constraints = _constraint_names("pt_telegram_bridge_outbox")
        if "uq_tg_bridge_outbox_project_dedupe" in outbox_constraints:
            op.drop_constraint("uq_tg_bridge_outbox_project_dedupe", "pt_telegram_bridge_outbox", type_="unique")

    if _has_table("pt_telegram_bridge_binding"):
        binding_constraints = _constraint_names("pt_telegram_bridge_binding")
        if "uq_tg_bridge_binding_project_topic" in binding_constraints:
            op.drop_constraint("uq_tg_bridge_binding_project_topic", "pt_telegram_bridge_binding", type_="unique")
        if "uq_tg_bridge_binding_project_source" in binding_constraints:
            op.drop_constraint("uq_tg_bridge_binding_project_source", "pt_telegram_bridge_binding", type_="unique")
