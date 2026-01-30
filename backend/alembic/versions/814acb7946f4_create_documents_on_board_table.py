"""create_documents_on_board_table

Revision ID: 814acb7946f4
Revises: 1d77b1401c16
Create Date: 2026-01-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '814acb7946f4'
down_revision: Union[str, Sequence[str], None] = '1d77b1401c16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create document_status enum type
    document_status_enum = postgresql.ENUM(
        'Active', 'Expired', 'Expiring Soon', 'Inactive',
        name='document_status',
        create_type=True
    )
    document_status_enum.create(op.get_bind(), checkfirst=True)

    # Create documents_on_board table
    op.create_table(
        'documents_on_board',
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('aircraft_id', sa.Integer(), nullable=False),
        sa.Column('document_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('warning_days', sa.Integer(), nullable=True),
        sa.Column('status', postgresql.ENUM('Active', 'Expired', 'Expiring Soon', 'Inactive', name='document_status', create_type=False), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['aircraft_id'], ['aircrafts.id'], ),
        sa.PrimaryKeyConstraint('document_id')
    )
    op.create_index(op.f('ix_documents_on_board_document_id'), 'documents_on_board', ['document_id'], unique=False)
    op.create_index(op.f('ix_documents_on_board_aircraft_id'), 'documents_on_board', ['aircraft_id'], unique=False)
    op.create_index(op.f('ix_documents_on_board_document_name'), 'documents_on_board', ['document_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_documents_on_board_document_name'), table_name='documents_on_board')
    op.drop_index(op.f('ix_documents_on_board_aircraft_id'), table_name='documents_on_board')
    op.drop_index(op.f('ix_documents_on_board_document_id'), table_name='documents_on_board')
    op.drop_table('documents_on_board')
    
    # Drop enum type
    document_status_enum = postgresql.ENUM(name='document_status', create_type=False)
    document_status_enum.drop(op.get_bind(), checkfirst=True)
