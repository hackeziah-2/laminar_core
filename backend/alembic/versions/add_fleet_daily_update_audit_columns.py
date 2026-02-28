"""add audit columns to fleet_daily_update

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fleet_daily_update",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "fleet_daily_update",
        sa.Column("updated_by", sa.Integer(), nullable=True),
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


def downgrade() -> None:
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
    op.drop_column("fleet_daily_update", "updated_by")
    op.drop_column("fleet_daily_update", "created_by")
