"""Initial slimmed-down schema for the TGO API service."""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import MetaData

from app.core.database import Base

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Snapshot the current SQLAlchemy metadata so future model changes
# do not retroactively mutate this baseline migration.
_snapshot_metadata = MetaData()
for table in Base.metadata.sorted_tables:
    table.tometadata(_snapshot_metadata)


def upgrade() -> None:
    """Create all tables defined in the snapshot metadata."""
    bind = op.get_bind()
    _snapshot_metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Drop all tables that were created by this migration."""
    bind = op.get_bind()
    _snapshot_metadata.drop_all(bind=bind, checkfirst=True)
