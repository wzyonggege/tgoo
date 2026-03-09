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

TABLE_NAME = "api_quick_replies"
INDEXES = (
    (
        "ix_api_quick_replies_project_id",
        "CREATE INDEX IF NOT EXISTS ix_api_quick_replies_project_id "
        "ON api_quick_replies (project_id)",
    ),
    (
        "ix_api_quick_replies_project_category",
        "CREATE INDEX IF NOT EXISTS ix_api_quick_replies_project_category "
        "ON api_quick_replies (project_id, category)",
    ),
    (
        "ix_api_quick_replies_project_active",
        "CREATE INDEX IF NOT EXISTS ix_api_quick_replies_project_active "
        "ON api_quick_replies (project_id, is_active)",
    ),
    (
        "uq_api_quick_replies_project_shortcut_active",
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_api_quick_replies_project_shortcut_active "
        "ON api_quick_replies (project_id, shortcut) "
        "WHERE deleted_at IS NULL",
    ),
)


def _create_indexes() -> None:
    for _, statement in INDEXES:
        op.execute(sa.text(statement))


def upgrade() -> None:
    """Create api_quick_replies table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("shortcut", sa.String(length=64), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("100"),
            ),
            sa.Column(
                "usage_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["api_staff.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["api_projects.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["updated_by"], ["api_staff.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_indexes()


def downgrade() -> None:
    """Drop api_quick_replies table."""
    for index_name, _ in reversed(INDEXES):
        op.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE_NAME}"))
