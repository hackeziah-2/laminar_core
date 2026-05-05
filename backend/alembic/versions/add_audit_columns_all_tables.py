"""Add created_by / updated_by (account_information) to all ORM tables.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-03-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that did not already have these columns in schema.
_TABLES = (
    "aircrafts",
    "airframe",
    "airframe_tables",
    "engine",
    "flights",
    "modules",
    "propeller",
    "roles",
    "users",
    "account_information",
    "ad_monitoring",
    "aircraft_logbook_entries",
    "documents_on_board",
    "ldnd_monitoring",
    "role_permissions",
    "airframe_logbook",
    "avionics_logbook",
    "engine_logbook",
    "propeller_logbook",
    "user_permissions",
    "workorder_ad_monitoring",
    "airframe_component_record",
    "avionics_component_record",
    "component_parts_record",
    "cpcp_monitoring",
    "engine_component_record",
    "tcc_maintenance",
    "personnel_compliance",
    "certificate_category_types",
    "organizational_approvals",
    "aircraft_statutory_certificates",
    "authorization_scope_cessna",
    "authorization_scope_baron",
    "authorization_scope_others",
    "personnel_authorization",
    "oem_item_types",
    "oem_technical_publications",
    "organizational_approvals_history",
    "aircraft_statutory_certificates_history",
)


def upgrade() -> None:
    # fleet_daily_update: align FKs with account_information (was users.id)
    op.execute(sa.text("UPDATE fleet_daily_update SET created_by = NULL, updated_by = NULL"))
    op.drop_constraint(
        "fk_fleet_daily_update_updated_by_users",
        "fleet_daily_update",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_fleet_daily_update_created_by_users",
        "fleet_daily_update",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_fleet_daily_update_created_by_acct",
        "fleet_daily_update",
        "account_information",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_fleet_daily_update_updated_by_acct",
        "fleet_daily_update",
        "account_information",
        ["updated_by"],
        ["id"],
    )

    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("created_by", sa.Integer(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("updated_by", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_created_by_acct",
            table,
            "account_information",
            ["created_by"],
            ["id"],
        )
        op.create_foreign_key(
            f"fk_{table}_updated_by_acct",
            table,
            "account_information",
            ["updated_by"],
            ["id"],
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_constraint(
            f"fk_{table}_updated_by_acct",
            table,
            type_="foreignkey",
        )
        op.drop_constraint(
            f"fk_{table}_created_by_acct",
            table,
            type_="foreignkey",
        )
        op.drop_column(table, "updated_by")
        op.drop_column(table, "created_by")

    op.drop_constraint(
        "fk_fleet_daily_update_updated_by_acct",
        "fleet_daily_update",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_fleet_daily_update_created_by_acct",
        "fleet_daily_update",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_fleet_daily_update_created_by_users",
        "fleet_daily_update",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_fleet_daily_update_updated_by_users",
        "fleet_daily_update",
        "users",
        ["updated_by"],
        ["id"],
    )
