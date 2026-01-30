"""change_status_to_boolean

Revision ID: change_status_to_boolean
Revises: add_account_fields
Create Date: 2025-01-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'change_status_to_boolean'
down_revision: Union[str, None] = 'add_account_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - convert status from enum to boolean."""
    # Add a temporary boolean column
    op.add_column(
        'account_information',
        sa.Column('status_temp', sa.Boolean(), nullable=True)
    )
    
    # Convert enum values to boolean:
    # 'active' -> True, 'inactive' or 'suspended' -> False
    op.execute("""
        UPDATE account_information 
        SET status_temp = CASE 
            WHEN status::text = 'active' THEN true 
            ELSE false 
        END
    """)
    
    # Make the temporary column non-nullable
    op.alter_column('account_information', 'status_temp', nullable=False)
    
    # Drop the old enum column
    op.drop_column('account_information', 'status')
    
    # Rename the temporary column to status using raw SQL
    op.execute('ALTER TABLE account_information RENAME COLUMN status_temp TO status')
    
    # Set default value for status column
    op.alter_column('account_information', 'status', server_default='true')
    
    # Drop the enum type (only if no other tables use it)
    op.execute('DROP TYPE IF EXISTS account_status')


def downgrade() -> None:
    """Downgrade schema - convert status back from boolean to enum."""
    # Recreate the enum type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE account_status AS ENUM ('active', 'inactive', 'suspended');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Add a temporary enum column
    op.add_column(
        'account_information',
        sa.Column(
            'status_temp',
            sa.Enum('active', 'inactive', 'suspended', name='account_status'),
            nullable=True
        )
    )
    
    # Convert boolean values back to enum:
    # True -> 'active', False -> 'inactive'
    op.execute("""
        UPDATE account_information 
        SET status_temp = CASE 
            WHEN status = true THEN 'active'::account_status
            ELSE 'inactive'::account_status
        END
    """)
    
    # Make the temporary column non-nullable
    op.alter_column('account_information', 'status_temp', nullable=False)
    
    # Drop the old boolean column
    op.drop_column('account_information', 'status')
    
    # Rename the temporary column to status using raw SQL
    op.execute('ALTER TABLE account_information RENAME COLUMN status_temp TO status')
    
    # Set default value for status column
    op.execute("ALTER TABLE account_information ALTER COLUMN status SET DEFAULT 'active'::account_status")
