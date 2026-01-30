"""add_remark_actiontaken_person_to_atl

Revision ID: dca4e2e7b88e
Revises: change_status_to_boolean
Create Date: 2026-01-23 02:43:52.875793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dca4e2e7b88e'
down_revision: Union[str, Sequence[str], None] = 'change_status_to_boolean'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add remark_person column
    op.add_column(
        'aircraft_technical_log',
        sa.Column('remark_person', sa.Integer(), nullable=True)
    )
    # Add foreign key constraint for remark_person
    op.create_foreign_key(
        'fk_remark_person_account',
        'aircraft_technical_log',
        'account_information',
        ['remark_person'],
        ['id']
    )

    # Add actiontaken_person column
    op.add_column(
        'aircraft_technical_log',
        sa.Column('actiontaken_person', sa.Integer(), nullable=True)
    )
    # Add foreign key constraint for actiontaken_person
    op.create_foreign_key(
        'fk_actiontaken_person_account',
        'aircraft_technical_log',
        'account_information',
        ['actiontaken_person'],
        ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop foreign key constraints
    op.drop_constraint('fk_actiontaken_person_account', 'aircraft_technical_log', type_='foreignkey')
    op.drop_constraint('fk_remark_person_account', 'aircraft_technical_log', type_='foreignkey')
    
    # Drop columns
    op.drop_column('aircraft_technical_log', 'actiontaken_person')
    op.drop_column('aircraft_technical_log', 'remark_person')
