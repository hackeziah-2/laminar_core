"""create_logbook_tables

Revision ID: 1d77b1401c16
Revises: 79a90c116644
Create Date: 2026-01-27 03:25:10.564456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d77b1401c16'
down_revision: Union[str, Sequence[str], None] = '79a90c116644'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create engine_logbook table
    op.create_table(
        'engine_logbook',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('engine_tsn', sa.Float(), nullable=True),
        sa.Column('sequence_no', sa.String(length=50), nullable=False),
        sa.Column('tach_time', sa.Float(), nullable=True),
        sa.Column('engine_tso', sa.Float(), nullable=True),
        sa.Column('engine_tbo', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mechanic_fk', sa.Integer(), nullable=True),
        sa.Column('signature', sa.String(length=255), nullable=True),
        sa.Column('upload_file', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['mechanic_fk'], ['account_information.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_engine_logbook_id'), 'engine_logbook', ['id'], unique=False)
    op.create_index(op.f('ix_engine_logbook_sequence_no'), 'engine_logbook', ['sequence_no'], unique=False)

    # Create airframe_logbook table
    op.create_table(
        'airframe_logbook',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('sequence_no', sa.String(length=50), nullable=False),
        sa.Column('tach_time', sa.Float(), nullable=True),
        sa.Column('airframe_time', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mechanic_fk', sa.Integer(), nullable=True),
        sa.Column('signature', sa.String(length=255), nullable=True),
        sa.Column('upload_file', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['mechanic_fk'], ['account_information.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_airframe_logbook_id'), 'airframe_logbook', ['id'], unique=False)
    op.create_index(op.f('ix_airframe_logbook_sequence_no'), 'airframe_logbook', ['sequence_no'], unique=False)

    # Create avionics_logbook table
    op.create_table(
        'avionics_logbook',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('airframe_tsn', sa.Float(), nullable=True),
        sa.Column('sequence_no', sa.String(length=50), nullable=False),
        sa.Column('component', sa.String(length=255), nullable=True),
        sa.Column('part_no', sa.String(length=100), nullable=True),
        sa.Column('serial_no', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mechanic_fk', sa.Integer(), nullable=True),
        sa.Column('signature', sa.String(length=255), nullable=True),
        sa.Column('upload_file', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['mechanic_fk'], ['account_information.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_avionics_logbook_id'), 'avionics_logbook', ['id'], unique=False)
    op.create_index(op.f('ix_avionics_logbook_sequence_no'), 'avionics_logbook', ['sequence_no'], unique=False)

    # Create propeller_logbook table
    op.create_table(
        'propeller_logbook',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('propeller_tsn', sa.Float(), nullable=True),
        sa.Column('sequence_no', sa.String(length=50), nullable=False),
        sa.Column('tach_time', sa.Float(), nullable=True),
        sa.Column('propeller_tso', sa.Float(), nullable=True),
        sa.Column('propeller_tbo', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mechanic_fk', sa.Integer(), nullable=True),
        sa.Column('signature', sa.String(length=255), nullable=True),
        sa.Column('upload_file', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['mechanic_fk'], ['account_information.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_propeller_logbook_id'), 'propeller_logbook', ['id'], unique=False)
    op.create_index(op.f('ix_propeller_logbook_sequence_no'), 'propeller_logbook', ['sequence_no'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_propeller_logbook_sequence_no'), table_name='propeller_logbook')
    op.drop_index(op.f('ix_propeller_logbook_id'), table_name='propeller_logbook')
    op.drop_table('propeller_logbook')
    
    op.drop_index(op.f('ix_avionics_logbook_sequence_no'), table_name='avionics_logbook')
    op.drop_index(op.f('ix_avionics_logbook_id'), table_name='avionics_logbook')
    op.drop_table('avionics_logbook')
    
    op.drop_index(op.f('ix_airframe_logbook_sequence_no'), table_name='airframe_logbook')
    op.drop_index(op.f('ix_airframe_logbook_id'), table_name='airframe_logbook')
    op.drop_table('airframe_logbook')
    
    op.drop_index(op.f('ix_engine_logbook_sequence_no'), table_name='engine_logbook')
    op.drop_index(op.f('ix_engine_logbook_id'), table_name='engine_logbook')
    op.drop_table('engine_logbook')
