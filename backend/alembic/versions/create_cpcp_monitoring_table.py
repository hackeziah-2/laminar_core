"""create cpcp_monitoring table

Revision ID: create_cpcp_monitoring
Revises: ec9a64edc639
Create Date: 2026-02-10

CPCP Monitoring: inspection_operation, description, interval_hours, interval_months,
last_done_tach, last_done_aftt, last_done_date, atl_ref (FK aircraft_technical_log).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "create_cpcp_monitoring"
down_revision: Union[str, Sequence[str], None] = "ec9a64edc639"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cpcp_monitoring",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("inspection_operation", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("interval_hours", sa.Float(), nullable=True),
        sa.Column("interval_months", sa.Float(), nullable=True),
        sa.Column("last_done_tach", sa.Float(), nullable=True),
        sa.Column("last_done_aftt", sa.Float(), nullable=True),
        sa.Column("last_done_date", sa.Date(), nullable=True),
        sa.Column("atl_ref", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["atl_ref"], ["aircraft_technical_log.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_cpcp_monitoring_id"), "cpcp_monitoring", ["id"], unique=False)
    op.create_index(op.f("ix_cpcp_monitoring_atl_ref"), "cpcp_monitoring", ["atl_ref"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cpcp_monitoring_atl_ref"), table_name="cpcp_monitoring")
    op.drop_index(op.f("ix_cpcp_monitoring_id"), table_name="cpcp_monitoring")
    op.drop_table("cpcp_monitoring")
