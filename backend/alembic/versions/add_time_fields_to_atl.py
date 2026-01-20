"""add_time_fields_to_atl

Revision ID: add_time_fields_to_atl
Revises: add_atl_ldnd_account
Create Date: 2025-01-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_time_fields_to_atl'
down_revision: Union[str, None] = 'add_atl_ldnd_account'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add airframe time fields
    op.add_column(
        'aircraft_technical_log',
        sa.Column('airframe_prev_time', sa.Float(), nullable=True)
    )
    op.add_column(
        'aircraft_technical_log',
        sa.Column('airframe_flight_time', sa.Float(), nullable=True)
    )
    op.add_column(
        'aircraft_technical_log',
        sa.Column('airframe_total_time', sa.Float(), nullable=True)
    )

    # Add engine time fields
    op.add_column(
        'aircraft_technical_log',
        sa.Column('engine_prev_time', sa.Float(), nullable=True)
    )
    op.add_column(
        'aircraft_technical_log',
        sa.Column('engine_flight_time', sa.Float(), nullable=True)
    )
    op.add_column(
        'aircraft_technical_log',
        sa.Column('engine_total_time', sa.Float(), nullable=True)
    )

    # Add propeller time fields
    op.add_column(
        'aircraft_technical_log',
        sa.Column('propeller_prev_time', sa.Float(), nullable=True)
    )
    op.add_column(
        'aircraft_technical_log',
        sa.Column('propeller_flight_time', sa.Float(), nullable=True)
    )
    op.add_column(
        'aircraft_technical_log',
        sa.Column('propeller_total_time', sa.Float(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove propeller time fields
    op.drop_column('aircraft_technical_log', 'propeller_total_time')
    op.drop_column('aircraft_technical_log', 'propeller_flight_time')
    op.drop_column('aircraft_technical_log', 'propeller_prev_time')

    # Remove engine time fields
    op.drop_column('aircraft_technical_log', 'engine_total_time')
    op.drop_column('aircraft_technical_log', 'engine_flight_time')
    op.drop_column('aircraft_technical_log', 'engine_prev_time')

    # Remove airframe time fields
    op.drop_column('aircraft_technical_log', 'airframe_total_time')
    op.drop_column('aircraft_technical_log', 'airframe_flight_time')
    op.drop_column('aircraft_technical_log', 'airframe_prev_time')
