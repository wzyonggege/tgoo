"""remove legacy ai-related tables"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0026_remove_legacy_ai_modules"
down_revision = "0025_rm_device_control_model"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

LEGACY_TABLES = [
    "api_ai_models",
    "api_project_ai_configs",
    "api_ai_providers",
    "api_project_onboarding_progress",
    "api_store_credentials",
    "api_toolstore_credentials",
    "api_visitor_ai_profiles",
    "api_visitor_ai_insights",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Drop ai_provider_id FK/index first so api_ai_providers can be removed safely.
    if "api_visitor_assignment_rules" in existing_tables:
        columns = {
            col["name"]
            for col in inspector.get_columns("api_visitor_assignment_rules")
        }
        if "ai_provider_id" in columns:
            op.drop_constraint(
                "api_visitor_assignment_rules_ai_provider_id_fkey",
                "api_visitor_assignment_rules",
                type_="foreignkey",
            )
            indexes = {
                idx["name"]
                for idx in inspector.get_indexes("api_visitor_assignment_rules")
            }
            if "ix_api_visitor_assignment_rules_ai_provider_id" in indexes:
                op.drop_index(
                    "ix_api_visitor_assignment_rules_ai_provider_id",
                    table_name="api_visitor_assignment_rules",
                )
            op.drop_column("api_visitor_assignment_rules", "ai_provider_id")

    for table_name in LEGACY_TABLES:
        if table_name in existing_tables:
            op.drop_table(table_name)

    # Drop legacy default_team_id column on projects
    if "api_projects" in existing_tables:
        project_columns = {col["name"] for col in inspector.get_columns("api_projects")}
        if "default_team_id" in project_columns:
            op.drop_column("api_projects", "default_team_id")


def downgrade() -> None:
    # The legacy tables are intentionally not recreated.
    # This downgrade is a no-op.
    pass
