"""Add display_order to tcc_maintenance and cpcp_monitoring

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-07-20

Persistent drag-and-drop row order for Maintenance TCC and CPCP.
Existing rows are backfilled per aircraft using current id order (1..N).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "y0z1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "x9y0z1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tcc_maintenance",
        sa.Column("display_order", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        WITH ordered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY aircraft_fk
                    ORDER BY id ASC
                ) AS rn
            FROM tcc_maintenance
        )
        UPDATE tcc_maintenance AS t
        SET display_order = ordered.rn
        FROM ordered
        WHERE t.id = ordered.id
        """
    )
    op.alter_column(
        "tcc_maintenance",
        "display_order",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        op.f("ix_tcc_maintenance_display_order"),
        "tcc_maintenance",
        ["display_order"],
        unique=False,
    )

    op.add_column(
        "cpcp_monitoring",
        sa.Column("display_order", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        WITH ordered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY aircraft_id
                    ORDER BY id ASC
                ) AS rn
            FROM cpcp_monitoring
        )
        UPDATE cpcp_monitoring AS c
        SET display_order = ordered.rn
        FROM ordered
        WHERE c.id = ordered.id
        """
    )
    op.alter_column(
        "cpcp_monitoring",
        "display_order",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        op.f("ix_cpcp_monitoring_display_order"),
        "cpcp_monitoring",
        ["display_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cpcp_monitoring_display_order"), table_name="cpcp_monitoring")
    op.drop_column("cpcp_monitoring", "display_order")
    op.drop_index(op.f("ix_tcc_maintenance_display_order"), table_name="tcc_maintenance")
    op.drop_column("tcc_maintenance", "display_order")
