"""add ad_monitoring_fk back to workorder_ad_monitoring

Revision ID: add_ad_monitoring_fk_back
Revises: drop_ad_monitoring_fk
Create Date: 2026-02-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_ad_monitoring_fk_back"
down_revision: Union[str, Sequence[str], None] = "drop_ad_monitoring_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workorder_ad_monitoring",
        sa.Column("ad_monitoring_fk", sa.Integer(), nullable=True),
    )
    # Backfill existing rows: set to first ad_monitoring id if any, so we can set NOT NULL
    op.execute(
        sa.text(
            "UPDATE workorder_ad_monitoring SET ad_monitoring_fk = (SELECT id FROM ad_monitoring LIMIT 1) WHERE ad_monitoring_fk IS NULL"
        )
    )
    op.alter_column(
        "workorder_ad_monitoring",
        "ad_monitoring_fk",
        existing_type=sa.Integer(),
        nullable=False,
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


def downgrade() -> None:
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
