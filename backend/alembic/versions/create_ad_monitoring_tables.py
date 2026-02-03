"""create ad_monitoring and workorder_ad_monitoring tables

Revision ID: ad_monitoring_tables
Revises: ldnd_unit_rename
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ad_monitoring_tables"
down_revision: Union[str, Sequence[str], None] = "ldnd_unit_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ad_monitoring",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aircraft_fk", sa.Integer(), nullable=False),
        sa.Column("ad_number", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("inspection_interval", sa.String(length=100), nullable=False),
        sa.Column("compli_date", sa.Date(), nullable=True),
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
            onupdate=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["aircraft_fk"], ["aircrafts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ad_monitoring_id"), "ad_monitoring", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_ad_monitoring_aircraft_fk"),
        "ad_monitoring",
        ["aircraft_fk"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ad_monitoring_ad_number"),
        "ad_monitoring",
        ["ad_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ad_monitoring_subject"),
        "ad_monitoring",
        ["subject"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ad_monitoring_inspection_interval"),
        "ad_monitoring",
        ["inspection_interval"],
        unique=False,
    )

    op.create_table(
        "workorder_ad_monitoring",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ad_monitoring_fk", sa.Integer(), nullable=False),
        sa.Column("work_order_number", sa.String(length=50), nullable=False),
        sa.Column("last_done_actt", sa.Float(), nullable=True),
        sa.Column("last_done_tach", sa.Float(), nullable=True),
        sa.Column("last_done_date", sa.Date(), nullable=True),
        sa.Column("next_done_actt", sa.Float(), nullable=True),
        sa.Column("tach", sa.Float(), nullable=True),
        sa.Column("atl_ref", sa.String(length=50), nullable=False),
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
            onupdate=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ad_monitoring_fk"], ["ad_monitoring.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workorder_ad_monitoring_id"),
        "workorder_ad_monitoring",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workorder_ad_monitoring_ad_monitoring_fk"),
        "workorder_ad_monitoring",
        ["ad_monitoring_fk"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workorder_ad_monitoring_work_order_number"),
        "workorder_ad_monitoring",
        ["work_order_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workorder_ad_monitoring_atl_ref"),
        "workorder_ad_monitoring",
        ["atl_ref"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workorder_ad_monitoring_atl_ref"),
        table_name="workorder_ad_monitoring",
    )
    op.drop_index(
        op.f("ix_workorder_ad_monitoring_work_order_number"),
        table_name="workorder_ad_monitoring",
    )
    op.drop_index(
        op.f("ix_workorder_ad_monitoring_ad_monitoring_fk"),
        table_name="workorder_ad_monitoring",
    )
    op.drop_index(
        op.f("ix_workorder_ad_monitoring_id"),
        table_name="workorder_ad_monitoring",
    )
    op.drop_table("workorder_ad_monitoring")

    op.drop_index(
        op.f("ix_ad_monitoring_inspection_interval"),
        table_name="ad_monitoring",
    )
    op.drop_index(op.f("ix_ad_monitoring_subject"), table_name="ad_monitoring")
    op.drop_index(op.f("ix_ad_monitoring_ad_number"), table_name="ad_monitoring")
    op.drop_index(op.f("ix_ad_monitoring_aircraft_fk"), table_name="ad_monitoring")
    op.drop_index(op.f("ix_ad_monitoring_id"), table_name="ad_monitoring")
    op.drop_table("ad_monitoring")
