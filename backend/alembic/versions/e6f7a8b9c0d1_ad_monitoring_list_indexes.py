"""Add AD monitoring list indexes for filter/sort pagination.

Revision ID: e6f7a8b9c0d1
Revises: dd3ee4ff5aa6
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "dd3ee4ff5aa6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ad_monitoring_aircraft_fk_created_at_active
        ON ad_monitoring (aircraft_fk, created_at)
        WHERE is_deleted IS FALSE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ad_monitoring_created_at_active
        ON ad_monitoring (created_at)
        WHERE is_deleted IS FALSE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ad_monitoring_compli_date_active
        ON ad_monitoring (compli_date)
        WHERE is_deleted IS FALSE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_workorder_ad_monitoring_ad_fk_created_at_active
        ON workorder_ad_monitoring (ad_monitoring_fk, created_at)
        WHERE is_deleted IS FALSE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_workorder_ad_monitoring_last_done_date_active
        ON workorder_ad_monitoring (last_done_date)
        WHERE is_deleted IS FALSE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_workorder_ad_monitoring_last_done_date_active")
    op.execute("DROP INDEX IF EXISTS ix_workorder_ad_monitoring_ad_fk_created_at_active")
    op.execute("DROP INDEX IF EXISTS ix_ad_monitoring_compli_date_active")
    op.execute("DROP INDEX IF EXISTS ix_ad_monitoring_created_at_active")
    op.execute("DROP INDEX IF EXISTS ix_ad_monitoring_aircraft_fk_created_at_active")
