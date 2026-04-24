"""fleet_daily_update: replace Running status with Operational

Revision ID: d3e4f5a6b7c8
Revises: c5d6e7f8a9b0
Create Date: 2026-04-24

Recreates fleet_daily_update_status_enum without "Running", maps existing
"Running" rows to "Operational", and sets the column default to Operational.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE fleet_daily_update_status_enum_new AS ENUM "
        "('Operational', 'Ongoing Maintenance', 'AOG')"
    )
    op.execute("ALTER TABLE fleet_daily_update ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE fleet_daily_update
        ALTER COLUMN status TYPE fleet_daily_update_status_enum_new
        USING (
            CASE status::text
                WHEN 'Running' THEN 'Operational'::fleet_daily_update_status_enum_new
                ELSE status::text::fleet_daily_update_status_enum_new
            END
        )
        """
    )
    op.execute("DROP TYPE fleet_daily_update_status_enum")
    op.execute("ALTER TYPE fleet_daily_update_status_enum_new RENAME TO fleet_daily_update_status_enum")
    op.execute(
        "ALTER TABLE fleet_daily_update ALTER COLUMN status "
        "SET DEFAULT 'Operational'::fleet_daily_update_status_enum"
    )


def downgrade() -> None:
    op.execute(
        "CREATE TYPE fleet_daily_update_status_enum_old AS ENUM "
        "('Running', 'Ongoing Maintenance', 'AOG')"
    )
    op.execute("ALTER TABLE fleet_daily_update ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE fleet_daily_update
        ALTER COLUMN status TYPE fleet_daily_update_status_enum_old
        USING (
            CASE status::text
                WHEN 'Operational' THEN 'Running'::fleet_daily_update_status_enum_old
                ELSE status::text::fleet_daily_update_status_enum_old
            END
        )
        """
    )
    op.execute("DROP TYPE fleet_daily_update_status_enum")
    op.execute("ALTER TYPE fleet_daily_update_status_enum_old RENAME TO fleet_daily_update_status_enum")
    op.execute(
        "ALTER TABLE fleet_daily_update ALTER COLUMN status "
        "SET DEFAULT 'Running'::fleet_daily_update_status_enum"
    )
