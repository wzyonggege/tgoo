"""Compatibility shim for removed Telegram topic bindings migration.

Revision ID: add_telegram_topic_bindings
Revises: add_slack_inbox
Create Date: 2026-04-19 22:05:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "add_telegram_topic_bindings"
down_revision = "add_slack_inbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This revision existed in a previous mistaken implementation.
    # Keep a no-op shim so existing databases/stamps can continue upgrading.
    pass


def downgrade() -> None:
    pass
