"""add_atl_ldnd_account

Revision ID: add_atl_ldnd_account
Revises: 0cb39712f865
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_atl_ldnd_account'
down_revision: Union[str, None] = '0cb39712f865'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create account_information table first since other tables
    # reference it
    op.create_table(
        'account_information',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'is_deleted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_account_information_id'),
        'account_information',
        ['id'],
        unique=False
    )

    # Create nature_of_flight enum type before using it in table
    nature_of_flight_enum = postgresql.ENUM(
        'TR',
        'PSF',
        'PRF',
        'EGR',
        'ME',
        'TR_WITH_PIREM',
        name='nature_of_flight',
        create_type=True
    )
    nature_of_flight_enum.create(op.get_bind(), checkfirst=True)

    # Create aircraft_technical_log table
    op.create_table(
        'aircraft_technical_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aircraft_fk', sa.Integer(), nullable=False),
        sa.Column('sequence_no', sa.String(length=50), nullable=False),
        sa.Column(
            'nature_of_flight',
            postgresql.ENUM(
                'TR',
                'PSF',
                'PRF',
                'EGR',
                'ME',
                'TR_WITH_PIREM',
                name='nature_of_flight',
                create_type=False
            ),
            server_default='TR',
            nullable=False
        ),
        sa.Column('next_inspection_due', sa.String(length=100),
                  nullable=True),
        sa.Column('tach_time_due', sa.Float(), nullable=True),
        sa.Column('origin_station', sa.String(length=50), nullable=False),
        sa.Column('origin_date', sa.Date(), nullable=False),
        sa.Column('origin_time', sa.Time(timezone=True), nullable=False),
        sa.Column('destination_station', sa.String(length=50),
                  nullable=False),
        sa.Column('destination_date', sa.Date(), nullable=False),
        sa.Column('destination_time', sa.Time(timezone=True),
                  nullable=False),
        sa.Column('number_of_landings', sa.Integer(), nullable=False),
        sa.Column('hobbs_meter_start', sa.Float(), nullable=False),
        sa.Column('hobbs_meter_end', sa.Float(), nullable=False),
        sa.Column('hobbs_meter_total', sa.Float(), nullable=False),
        sa.Column('tachometer_start', sa.Float(), nullable=False),
        sa.Column('tachometer_end', sa.Float(), nullable=False),
        sa.Column('tachometer_total', sa.Float(), nullable=False),
        sa.Column('fuel_qty_left_uplift_qty', sa.Float(), nullable=True),
        sa.Column('fuel_qty_right_uplift_qty', sa.Float(), nullable=True),
        sa.Column('fuel_qty_left_prior_departure', sa.Float(),
                  nullable=True),
        sa.Column('fuel_qty_right_prior_departure', sa.Float(),
                  nullable=True),
        sa.Column('fuel_qty_left_after_on_blks', sa.Float(), nullable=True),
        sa.Column('fuel_qty_right_after_on_blks', sa.Float(), nullable=True),
        sa.Column('oil_qty_uplift_qty', sa.Float(), nullable=True),
        sa.Column('oil_qty_prior_departure', sa.Float(), nullable=True),
        sa.Column('oil_qty_after_on_blks', sa.Float(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('actions_taken', sa.Text(), nullable=True),
        sa.Column('pilot_fk', sa.Integer(), nullable=True),
        sa.Column('maintenance_fk', sa.Integer(), nullable=True),
        sa.Column('pilot_accepted_by', sa.Integer(), nullable=True),
        sa.Column('pilot_accept_date', sa.Date(), nullable=True),
        sa.Column('pilot_accept_time', sa.Time(timezone=True),
                  nullable=True),
        sa.Column('rts_signed_by', sa.Integer(), nullable=True),
        sa.Column('rts_date', sa.Date(), nullable=True),
        sa.Column('rts_time', sa.Time(timezone=True), nullable=True),
        sa.Column('white_atl', sa.Text(), nullable=True),
        sa.Column('dfp', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'is_deleted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False
        ),
        sa.ForeignKeyConstraint(['aircraft_fk'], ['aircrafts.id'],
                                ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['pilot_fk'], ['account_information.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['maintenance_fk'],
                                ['account_information.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['pilot_accepted_by'],
                                ['account_information.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rts_signed_by'],
                                ['account_information.id'],
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    # Create indexes for foreign keys and frequently queried columns
    op.create_index(
        op.f('ix_aircraft_technical_log_id'),
        'aircraft_technical_log',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_aircraft_technical_log_aircraft_fk'),
        'aircraft_technical_log',
        ['aircraft_fk'],
        unique=False
    )
    op.create_index(
        op.f('ix_aircraft_technical_log_pilot_fk'),
        'aircraft_technical_log',
        ['pilot_fk'],
        unique=False
    )
    op.create_index(
        op.f('ix_aircraft_technical_log_sequence_no'),
        'aircraft_technical_log',
        ['sequence_no'],
        unique=False
    )

    # Create component_parts_record table
    op.create_table(
        'component_parts_record',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('atl_fk', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('nomenclature', sa.String(length=255), nullable=False),
        sa.Column('removed_part_no', sa.String(length=100), nullable=True),
        sa.Column('removed_serial_no', sa.String(length=100), nullable=True),
        sa.Column('installed_part_no', sa.String(length=100), nullable=True),
        sa.Column('installed_serial_no', sa.String(length=100),
                  nullable=True),
        sa.Column('part_description', sa.Text(), nullable=True),
        sa.Column('ata_chapter', sa.String(length=50), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'is_deleted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False
        ),
        sa.ForeignKeyConstraint(['atl_fk'], ['aircraft_technical_log.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_component_parts_record_id'),
        'component_parts_record',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_component_parts_record_atl_fk'),
        'component_parts_record',
        ['atl_fk'],
        unique=False
    )

    # Create ldnd_monitoring table
    op.create_table(
        'ldnd_monitoring',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aircraft_fk', sa.Integer(), nullable=False),
        sa.Column('inspection_type', sa.String(length=100), nullable=False),
        sa.Column('last_done_tach_due', sa.Float(), nullable=True),
        sa.Column('last_done_tach_done', sa.Float(), nullable=True),
        sa.Column('date_performed_start', sa.Date(), nullable=True),
        sa.Column('date_performed_end', sa.Date(), nullable=True),
        sa.Column('next_due', sa.Float(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'is_deleted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False
        ),
        sa.ForeignKeyConstraint(['aircraft_fk'], ['aircrafts.id'],
                                ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_ldnd_monitoring_id'),
        'ldnd_monitoring',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_ldnd_monitoring_aircraft_fk'),
        'ldnd_monitoring',
        ['aircraft_fk'],
        unique=False
    )
    op.create_index(
        op.f('ix_ldnd_monitoring_inspection_type'),
        'ldnd_monitoring',
        ['inspection_type'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_index(
        op.f('ix_ldnd_monitoring_inspection_type'),
        table_name='ldnd_monitoring'
    )
    op.drop_index(
        op.f('ix_ldnd_monitoring_aircraft_fk'),
        table_name='ldnd_monitoring'
    )
    op.drop_index(
        op.f('ix_ldnd_monitoring_id'),
        table_name='ldnd_monitoring'
    )
    op.drop_table('ldnd_monitoring')

    op.drop_index(
        op.f('ix_component_parts_record_atl_fk'),
        table_name='component_parts_record'
    )
    op.drop_index(
        op.f('ix_component_parts_record_id'),
        table_name='component_parts_record'
    )
    op.drop_table('component_parts_record')

    op.drop_index(
        op.f('ix_aircraft_technical_log_sequence_no'),
        table_name='aircraft_technical_log'
    )
    op.drop_index(
        op.f('ix_aircraft_technical_log_pilot_fk'),
        table_name='aircraft_technical_log'
    )
    op.drop_index(
        op.f('ix_aircraft_technical_log_aircraft_fk'),
        table_name='aircraft_technical_log'
    )
    op.drop_index(
        op.f('ix_aircraft_technical_log_id'),
        table_name='aircraft_technical_log'
    )
    op.drop_table('aircraft_technical_log')

    # Drop enum type after table is dropped
    op.execute("DROP TYPE IF EXISTS nature_of_flight")

    op.drop_index(
        op.f('ix_account_information_id'),
        table_name='account_information'
    )
    op.drop_table('account_information')
