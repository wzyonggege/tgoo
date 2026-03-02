"""Add quick replies table.

Revision ID: 20260302_0002
Revises: 0001_initial_schema
Create Date: 2026-03-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260302_0002"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_quick_replies table."""
    op.create_table(
        "api_quick_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("shortcut", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["api_staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["api_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["api_staff.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_api_quick_replies_project_id",
        "api_quick_replies",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_api_quick_replies_project_category",
        "api_quick_replies",
        ["project_id", "category"],
        unique=False,
    )
    op.create_index(
        "ix_api_quick_replies_project_active",
        "api_quick_replies",
        ["project_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "uq_api_quick_replies_project_shortcut_active",
        "api_quick_replies",
        ["project_id", "shortcut"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Drop api_quick_replies table."""
    op.drop_index("uq_api_quick_replies_project_shortcut_active", table_name="api_quick_replies")
    op.drop_index("ix_api_quick_replies_project_active", table_name="api_quick_replies")
    op.drop_index("ix_api_quick_replies_project_category", table_name="api_quick_replies")
    op.drop_index("ix_api_quick_replies_project_id", table_name="api_quick_replies")
    op.drop_table("api_quick_replies")
