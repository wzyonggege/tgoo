"""Add visitor ai reply override.

Revision ID: 20260314_0003
Revises: 20260302_0002
Create Date: 2026-03-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260314_0003"
down_revision: Union[str, None] = "20260302_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "api_visitors"
COLUMN_NAME = "ai_reply_id"


def upgrade() -> None:
    """Add visitor-level AI reply override column."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(COLUMN_NAME, sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    """Drop visitor-level AI reply override column."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME in columns:
        op.drop_column(TABLE_NAME, COLUMN_NAME)
