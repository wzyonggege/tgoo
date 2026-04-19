"""Switch project bridge config from telegram platform reference to bot token.

Revision ID: 20260419_0006
Revises: 20260419_0005
Create Date: 2026-04-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260419_0006"
down_revision: Union[str, None] = "20260419_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "api_projects"
FK_NAME = "fk_api_projects_bridge_telegram_platform_id"


def _column_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(TABLE_NAME)}


def _foreign_keys() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {fk["name"] for fk in inspector.get_foreign_keys(TABLE_NAME) if fk.get("name")}


def upgrade() -> None:
    columns = _column_names()
    foreign_keys = _foreign_keys()

    if "bridge_bot_token" not in columns:
        op.add_column(TABLE_NAME, sa.Column("bridge_bot_token", sa.String(length=255), nullable=True))

    if FK_NAME in foreign_keys:
        op.drop_constraint(FK_NAME, TABLE_NAME, type_="foreignkey")

    if "bridge_telegram_platform_id" in _column_names():
        op.drop_column(TABLE_NAME, "bridge_telegram_platform_id")


def downgrade() -> None:
    columns = _column_names()

    if "bridge_telegram_platform_id" not in columns:
        op.add_column(TABLE_NAME, sa.Column("bridge_telegram_platform_id", postgresql.UUID(as_uuid=True), nullable=True))

    if FK_NAME not in _foreign_keys():
        op.create_foreign_key(
            FK_NAME,
            TABLE_NAME,
            "api_platforms",
            ["bridge_telegram_platform_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "bridge_bot_token" in _column_names():
        op.drop_column(TABLE_NAME, "bridge_bot_token")
