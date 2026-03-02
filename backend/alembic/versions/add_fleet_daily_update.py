"""add fleet_daily_update table

Revision ID: a1b2c3d4e5f6
Revises: 79028bc1e0ad
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "79028bc1e0ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    fleet_daily_update_status_enum = postgresql.ENUM(
        "Running",
        "Ongoing Maintenance",
        "AOG",
        name="fleet_daily_update_status_enum",
        create_type=True,
    )
    fleet_daily_update_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "fleet_daily_update",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aircraft_fk", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "Running",
                "Ongoing Maintenance",
                "AOG",
                name="fleet_daily_update_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="Running",
        ),
        sa.Column("next_insp_due", sa.Float(), nullable=True),
        sa.Column("tach_time_due", sa.Float(), nullable=True),
        sa.Column("tach_time_eod", sa.Float(), nullable=True),
        sa.Column("remaining_time_before_next_isp", sa.Float(), nullable=True),
        sa.Column("remaining_time_before_engine", sa.Float(), nullable=True),
        sa.Column("remaining_time_before_propeller", sa.Float(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["aircraft_fk"], ["aircrafts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fleet_daily_update_id"), "fleet_daily_update", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_fleet_daily_update_aircraft_fk"),
        "fleet_daily_update",
        ["aircraft_fk"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_fleet_daily_update_aircraft_fk"), table_name="fleet_daily_update"
    )
    op.drop_index(op.f("ix_fleet_daily_update_id"), table_name="fleet_daily_update")
    op.drop_table("fleet_daily_update")
    op.execute("DROP TYPE IF EXISTS fleet_daily_update_status_enum")
