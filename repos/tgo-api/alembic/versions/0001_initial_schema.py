"""Initial slimmed-down schema for the TGO API service."""

from collections.abc import Iterable
from typing import Sequence, Union

from alembic import op
from sqlalchemy import MetaData, Table

from app.core.database import Base

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Freeze the set of tables that belonged to the initial schema.
#
# This migration originally copied every table from the live SQLAlchemy
# metadata, which allowed later models to leak into the baseline on fresh
# installs. Keep the table list static so follow-up revisions remain the
# only place where new tables are introduced.
_INITIAL_SCHEMA_TABLES = frozenset(
    {
        "api_channel_members",
        "api_channel_memory_clearances",
        "api_chat_files",
        "api_permissions",
        "api_platform_types",
        "api_platforms",
        "api_project_role_permissions",
        "api_projects",
        "api_role_permissions",
        "api_staff",
        "api_system_setup",
        "api_tags",
        "api_visitor_activities",
        "api_visitor_assignment_history",
        "api_visitor_assignment_rules",
        "api_visitor_customer_updates",
        "api_visitor_sessions",
        "api_visitor_system_info",
        "api_visitor_tags",
        "api_visitor_waiting_queue",
        "api_visitors",
    }
)


def _iter_initial_tables() -> Iterable[Table]:
    return (
        table
        for table in Base.metadata.sorted_tables
        if table.name in _INITIAL_SCHEMA_TABLES
    )


_snapshot_metadata = MetaData()
for table in _iter_initial_tables():
    table.to_metadata(_snapshot_metadata)


def upgrade() -> None:
    """Create all tables defined in the snapshot metadata."""
    bind = op.get_bind()
    _snapshot_metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Drop all tables that were created by this migration."""
    bind = op.get_bind()
    _snapshot_metadata.drop_all(bind=bind, checkfirst=True)
