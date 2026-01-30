"""change_time_columns_to_no_timezone

Revision ID: 79a90c116644
Revises: dca4e2e7b88e
Create Date: 2026-01-23 05:45:28.745247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79a90c116644'
down_revision: Union[str, Sequence[str], None] = 'dca4e2e7b88e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Change TIME WITH TIME ZONE to TIME (without timezone) for all time columns
    # PostgreSQL requires casting when changing from TIME WITH TIME ZONE to TIME
    op.execute("""
        ALTER TABLE aircraft_technical_log 
        ALTER COLUMN origin_time TYPE TIME USING (origin_time::TIME),
        ALTER COLUMN destination_time TYPE TIME USING (destination_time::TIME),
        ALTER COLUMN pilot_accept_time TYPE TIME USING (pilot_accept_time::TIME),
        ALTER COLUMN rts_time TYPE TIME USING (rts_time::TIME)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Change TIME back to TIME WITH TIME ZONE
    op.execute("""
        ALTER TABLE aircraft_technical_log 
        ALTER COLUMN origin_time TYPE TIME WITH TIME ZONE USING (origin_time::TIME WITH TIME ZONE),
        ALTER COLUMN destination_time TYPE TIME WITH TIME ZONE USING (destination_time::TIME WITH TIME ZONE),
        ALTER COLUMN pilot_accept_time TYPE TIME WITH TIME ZONE USING (pilot_accept_time::TIME WITH TIME ZONE),
        ALTER COLUMN rts_time TYPE TIME WITH TIME ZONE USING (rts_time::TIME WITH TIME ZONE)
    """)
