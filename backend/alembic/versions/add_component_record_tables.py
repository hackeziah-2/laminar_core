"""add component_record tables (engine, airframe, avionics)

Revision ID: add_component_record
Revises: add_ad_monitoring_fk_back
Create Date: 2026-02-04

One-to-many: EngineLogbook -> EngineComponentRecord, AirframeLogbook -> AirframeComponentRecord, AvionicsLogbook -> AvionicsComponentRecord.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_component_record"
down_revision: Union[str, Sequence[str], None] = "add_ad_monitoring_fk_back"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engine_component_record",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("engine_log_fk", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("nomenclature", sa.String(length=255), nullable=False),
        sa.Column("removed_part_no", sa.String(length=100), nullable=True),
        sa.Column("removed_serial_no", sa.String(length=100), nullable=True),
        sa.Column("installed_part_no", sa.String(length=100), nullable=True),
        sa.Column("installed_serial_no", sa.String(length=100), nullable=True),
        sa.Column("ata_chapter", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["engine_log_fk"], ["engine_logbook.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_engine_component_record_id"), "engine_component_record", ["id"], unique=False)
    op.create_index(op.f("ix_engine_component_record_engine_log_fk"), "engine_component_record", ["engine_log_fk"], unique=False)

    op.create_table(
        "airframe_component_record",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("airframe_log_fk", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("nomenclature", sa.String(length=255), nullable=False),
        sa.Column("removed_part_no", sa.String(length=100), nullable=True),
        sa.Column("removed_serial_no", sa.String(length=100), nullable=True),
        sa.Column("installed_part_no", sa.String(length=100), nullable=True),
        sa.Column("installed_serial_no", sa.String(length=100), nullable=True),
        sa.Column("ata_chapter", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["airframe_log_fk"], ["airframe_logbook.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_airframe_component_record_id"), "airframe_component_record", ["id"], unique=False)
    op.create_index(op.f("ix_airframe_component_record_airframe_log_fk"), "airframe_component_record", ["airframe_log_fk"], unique=False)

    op.create_table(
        "avionics_component_record",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("avionics_log_fk", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("nomenclature", sa.String(length=255), nullable=False),
        sa.Column("removed_part_no", sa.String(length=100), nullable=True),
        sa.Column("removed_serial_no", sa.String(length=100), nullable=True),
        sa.Column("installed_part_no", sa.String(length=100), nullable=True),
        sa.Column("installed_serial_no", sa.String(length=100), nullable=True),
        sa.Column("ata_chapter", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["avionics_log_fk"], ["avionics_logbook.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_avionics_component_record_id"), "avionics_component_record", ["id"], unique=False)
    op.create_index(op.f("ix_avionics_component_record_avionics_log_fk"), "avionics_component_record", ["avionics_log_fk"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_avionics_component_record_avionics_log_fk"), table_name="avionics_component_record")
    op.drop_index(op.f("ix_avionics_component_record_id"), table_name="avionics_component_record")
    op.drop_table("avionics_component_record")
    op.drop_index(op.f("ix_airframe_component_record_airframe_log_fk"), table_name="airframe_component_record")
    op.drop_index(op.f("ix_airframe_component_record_id"), table_name="airframe_component_record")
    op.drop_table("airframe_component_record")
    op.drop_index(op.f("ix_engine_component_record_engine_log_fk"), table_name="engine_component_record")
    op.drop_index(op.f("ix_engine_component_record_id"), table_name="engine_component_record")
    op.drop_table("engine_component_record")
