"""Add project-level Telegram bridge config fields.

Revision ID: 20260419_0005
Revises: 20260316_0004
Create Date: 2026-04-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260419_0005"
down_revision: Union[str, None] = "20260316_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "api_projects"


def _column_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(TABLE_NAME)}


def _foreign_keys() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {fk["name"] for fk in inspector.get_foreign_keys(TABLE_NAME) if fk.get("name")}


def upgrade() -> None:
    """Add project-level Telegram bridge config columns."""
    columns = _column_names()

    if "bridge_enabled" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "bridge_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if "bridge_telegram_platform_id" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "bridge_telegram_platform_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )

    if "bridge_chat_id" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("bridge_chat_id", sa.String(length=255), nullable=True),
        )

    if "bridge_admin_only" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "bridge_admin_only",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )

    foreign_keys = _foreign_keys()
    fk_name = "fk_api_projects_bridge_telegram_platform_id"
    if "bridge_telegram_platform_id" in _column_names() and fk_name not in foreign_keys:
        op.create_foreign_key(
            fk_name,
            TABLE_NAME,
            "api_platforms",
            ["bridge_telegram_platform_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Drop project-level Telegram bridge config columns."""
    foreign_keys = _foreign_keys()
    fk_name = "fk_api_projects_bridge_telegram_platform_id"
    if fk_name in foreign_keys:
        op.drop_constraint(fk_name, TABLE_NAME, type_="foreignkey")

    columns = _column_names()
    for column_name in (
        "bridge_admin_only",
        "bridge_chat_id",
        "bridge_telegram_platform_id",
        "bridge_enabled",
    ):
        if column_name in columns:
            op.drop_column(TABLE_NAME, column_name)
