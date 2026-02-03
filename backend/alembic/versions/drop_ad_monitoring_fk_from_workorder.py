"""drop ad_monitoring_fk from workorder_ad_monitoring

Revision ID: drop_ad_monitoring_fk
Revises: ad_monitoring_tables
Create Date: 2026-02-03

"""
from typing import Sequence, Union

from alembic import op


revision: str = "drop_ad_monitoring_fk"
down_revision: Union[str, Sequence[str], None] = "ad_monitoring_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "workorder_ad_monitoring_ad_monitoring_fk_fkey",
        "workorder_ad_monitoring",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_workorder_ad_monitoring_ad_monitoring_fk"),
        table_name="workorder_ad_monitoring",
    )
    op.drop_column("workorder_ad_monitoring", "ad_monitoring_fk")


def downgrade() -> None:
    op.add_column(
        "workorder_ad_monitoring",
        op.Column("ad_monitoring_fk", op.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_workorder_ad_monitoring_ad_monitoring_fk"),
        "workorder_ad_monitoring",
        ["ad_monitoring_fk"],
        unique=False,
    )
    op.create_foreign_key(
        "workorder_ad_monitoring_ad_monitoring_fk_fkey",
        "workorder_ad_monitoring",
        "ad_monitoring",
        ["ad_monitoring_fk"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column(
        "workorder_ad_monitoring",
        "ad_monitoring_fk",
        existing_type=op.Integer(),
        nullable=False,
    )
