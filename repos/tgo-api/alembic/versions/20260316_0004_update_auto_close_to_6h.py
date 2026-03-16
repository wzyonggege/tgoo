"""Update auto close defaults to 6 hours and restore AI after close.

Revision ID: 20260316_0004
Revises: 20260314_0003
Create Date: 2026-03-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260316_0004"
down_revision: Union[str, None] = "20260314_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update existing assignment rules to 6h when they still use the old default."""
    op.execute(
        sa.text(
            """
            UPDATE api_visitor_assignment_rules
            SET auto_close_hours = 6
            WHERE auto_close_hours IS NULL OR auto_close_hours = 48
            """
        )
    )


def downgrade() -> None:
    """Restore previous default-like values back to 48h."""
    op.execute(
        sa.text(
            """
            UPDATE api_visitor_assignment_rules
            SET auto_close_hours = 48
            WHERE auto_close_hours = 6
            """
        )
    )
