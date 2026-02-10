"""create tcc_maintenance table

Revision ID: create_setting_tcc_maintenance
Revises: add_file_path_ad_monitoring
Create Date: 2026-02-10

Table: tcc_maintenance with method_of_compliance_enum (Overhaul, Replacement, Inspection, I&S, Operational Test, Calibration).
FKs: aircrafts.id, aircraft_technical_log.id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "create_setting_tcc_maintenance"
down_revision: Union[str, Sequence[str], None] = "add_file_path_ad_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type first (checkfirst=True so no error if it already exists)
    method_of_compliance_enum_create = postgresql.ENUM(
        "Overhaul",
        "Replacement",
        "Inspection",
        "I&S",
        "Operational Test",
        "Calibration",
        name="method_of_compliance_enum",
        create_type=True,
    )
    method_of_compliance_enum_create.create(op.get_bind(), checkfirst=True)

    # Use create_type=False in table so SQLAlchemy does not try to create the type again
    method_of_compliance_enum = postgresql.ENUM(
        "Overhaul",
        "Replacement",
        "Inspection",
        "I&S",
        "Operational Test",
        "Calibration",
        name="method_of_compliance_enum",
        create_type=False,
    )

    op.create_table(
        "tcc_maintenance",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("part_number", sa.String(), nullable=False),
        sa.Column("serial_number", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("component_limit_years", sa.Integer(), nullable=True),
        sa.Column("component_limit_hours", sa.Float(), nullable=True),
        sa.Column(
            "component_method_of_compliance",
            method_of_compliance_enum,
            nullable=True,
        ),
        sa.Column("last_done_date", sa.Date(), nullable=True),
        sa.Column("last_done_tach", sa.Float(), nullable=True),
        sa.Column("last_done_aftt", sa.Float(), nullable=True),
        sa.Column(
            "last_done_method_of_compliance",
            method_of_compliance_enum,
            nullable=True,
        ),
        sa.Column("aircraft_fk", sa.Integer(), nullable=False),
        sa.Column("atl_ref", sa.Integer(), nullable=False),
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
            server_default=sa.false(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["aircraft_fk"], ["aircrafts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["atl_ref"], ["aircraft_technical_log.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tcc_maintenance_id"),
        "tcc_maintenance",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tcc_maintenance_aircraft_fk"),
        "tcc_maintenance",
        ["aircraft_fk"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tcc_maintenance_atl_ref"),
        "tcc_maintenance",
        ["atl_ref"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tcc_maintenance_atl_ref"),
        table_name="tcc_maintenance",
    )
    op.drop_index(
        op.f("ix_tcc_maintenance_aircraft_fk"),
        table_name="tcc_maintenance",
    )
    op.drop_index(
        op.f("ix_tcc_maintenance_id"),
        table_name="tcc_maintenance",
    )
    op.drop_table("tcc_maintenance")
    method_of_compliance_enum = postgresql.ENUM(
        name="method_of_compliance_enum", create_type=False
    )
    method_of_compliance_enum.drop(op.get_bind(), checkfirst=True)
