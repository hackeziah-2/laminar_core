"""add aircraft_fk to logbook tables

Revision ID: add_aircraft_fk_logbooks
Revises: 814acb7946f4
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_aircraft_fk_logbooks'
down_revision: Union[str, Sequence[str], None] = '814acb7946f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add aircraft_fk column to engine_logbook, airframe_logbook, avionics_logbook, propeller_logbook."""
    # Add as nullable=True for existing rows; set nullable=False in app model for new inserts.
    op.add_column('engine_logbook', sa.Column('aircraft_fk', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_engine_logbook_aircraft_fk', 'engine_logbook', 'aircrafts',
        ['aircraft_fk'], ['id']
    )
    op.create_index(op.f('ix_engine_logbook_aircraft_fk'), 'engine_logbook', ['aircraft_fk'], unique=False)

    op.add_column('airframe_logbook', sa.Column('aircraft_fk', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_airframe_logbook_aircraft_fk', 'airframe_logbook', 'aircrafts',
        ['aircraft_fk'], ['id']
    )
    op.create_index(op.f('ix_airframe_logbook_aircraft_fk'), 'airframe_logbook', ['aircraft_fk'], unique=False)

    op.add_column('avionics_logbook', sa.Column('aircraft_fk', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_avionics_logbook_aircraft_fk', 'avionics_logbook', 'aircrafts',
        ['aircraft_fk'], ['id']
    )
    op.create_index(op.f('ix_avionics_logbook_aircraft_fk'), 'avionics_logbook', ['aircraft_fk'], unique=False)

    op.add_column('propeller_logbook', sa.Column('aircraft_fk', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_propeller_logbook_aircraft_fk', 'propeller_logbook', 'aircrafts',
        ['aircraft_fk'], ['id']
    )
    op.create_index(op.f('ix_propeller_logbook_aircraft_fk'), 'propeller_logbook', ['aircraft_fk'], unique=False)


def downgrade() -> None:
    """Remove aircraft_fk from logbook tables."""
    op.drop_index(op.f('ix_propeller_logbook_aircraft_fk'), table_name='propeller_logbook')
    op.drop_constraint('fk_propeller_logbook_aircraft_fk', 'propeller_logbook', type_='foreignkey')
    op.drop_column('propeller_logbook', 'aircraft_fk')

    op.drop_index(op.f('ix_avionics_logbook_aircraft_fk'), table_name='avionics_logbook')
    op.drop_constraint('fk_avionics_logbook_aircraft_fk', 'avionics_logbook', type_='foreignkey')
    op.drop_column('avionics_logbook', 'aircraft_fk')

    op.drop_index(op.f('ix_airframe_logbook_aircraft_fk'), table_name='airframe_logbook')
    op.drop_constraint('fk_airframe_logbook_aircraft_fk', 'airframe_logbook', type_='foreignkey')
    op.drop_column('airframe_logbook', 'aircraft_fk')

    op.drop_index(op.f('ix_engine_logbook_aircraft_fk'), table_name='engine_logbook')
    op.drop_constraint('fk_engine_logbook_aircraft_fk', 'engine_logbook', type_='foreignkey')
    op.drop_column('engine_logbook', 'aircraft_fk')
