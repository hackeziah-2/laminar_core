"""add_fields_to_account_information

Revision ID: add_account_fields
Revises: add_time_fields_to_atl
Create Date: 2025-01-27 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_account_fields'
down_revision: Union[str, None] = 'add_time_fields_to_atl'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create account_status enum type (check first to avoid errors)
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE account_status AS ENUM ('active', 'inactive', 'suspended');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # Add first_name column (nullable first, then update and make non-nullable)
    op.add_column(
        'account_information',
        sa.Column('first_name', sa.String(length=100), nullable=True)
    )
    # Set default for existing records
    op.execute("UPDATE account_information SET first_name = 'Unknown' WHERE first_name IS NULL")
    # Make it non-nullable
    op.alter_column('account_information', 'first_name', nullable=False)
    op.create_index(
        op.f('ix_account_information_first_name'),
        'account_information',
        ['first_name'],
        unique=False
    )

    # Add last_name column (nullable first, then update and make non-nullable)
    op.add_column(
        'account_information',
        sa.Column('last_name', sa.String(length=100), nullable=True)
    )
    # Set default for existing records
    op.execute("UPDATE account_information SET last_name = 'Unknown' WHERE last_name IS NULL")
    # Make it non-nullable
    op.alter_column('account_information', 'last_name', nullable=False)
    op.create_index(
        op.f('ix_account_information_last_name'),
        'account_information',
        ['last_name'],
        unique=False
    )

    # Add middle_name column
    op.add_column(
        'account_information',
        sa.Column('middle_name', sa.String(length=100), nullable=True)
    )

    # Add username column (nullable first, then update and make non-nullable)
    op.add_column(
        'account_information',
        sa.Column('username', sa.String(length=100), nullable=True)
    )
    # Set default for existing records (use id as fallback)
    op.execute(
        "UPDATE account_information SET username = 'user_' || id::text WHERE username IS NULL"
    )
    # Make it non-nullable
    op.alter_column('account_information', 'username', nullable=False)
    op.create_index(
        op.f('ix_account_information_username'),
        'account_information',
        ['username'],
        unique=True
    )

    # Add password column (nullable first, then update and make non-nullable)
    op.add_column(
        'account_information',
        sa.Column('password', sa.String(length=255), nullable=True)
    )
    # Set default for existing records (hash of 'changeme')
    op.execute(
        "UPDATE account_information SET password = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5Gy5zZQf.1234' WHERE password IS NULL"
    )
    # Make it non-nullable
    op.alter_column('account_information', 'password', nullable=False)

    # Add designation column
    op.add_column(
        'account_information',
        sa.Column('designation', sa.String(length=100), nullable=True)
    )

    # Add license_no column
    op.add_column(
        'account_information',
        sa.Column('license_no', sa.String(length=100), nullable=True)
    )
    op.create_index(
        op.f('ix_account_information_license_no'),
        'account_information',
        ['license_no'],
        unique=False
    )

    # Add auth_stamp column
    op.add_column(
        'account_information',
        sa.Column('auth_stamp', sa.String(length=255), nullable=True)
    )

    # Add status column
    op.add_column(
        'account_information',
        sa.Column(
            'status',
            postgresql.ENUM(
                'active',
                'inactive',
                'suspended',
                name='account_status',
                create_type=False,
                values_callable=lambda x: x
            ),
            server_default='active',
            nullable=False
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove status column
    op.drop_column('account_information', 'status')

    # Remove auth_stamp column
    op.drop_column('account_information', 'auth_stamp')

    # Remove license_no column and index
    op.drop_index(
        op.f('ix_account_information_license_no'),
        table_name='account_information'
    )
    op.drop_column('account_information', 'license_no')

    # Remove designation column
    op.drop_column('account_information', 'designation')

    # Remove password column
    op.drop_column('account_information', 'password')

    # Remove username column and index
    op.drop_index(
        op.f('ix_account_information_username'),
        table_name='account_information'
    )
    op.drop_column('account_information', 'username')

    # Remove middle_name column
    op.drop_column('account_information', 'middle_name')

    # Remove last_name column and index
    op.drop_index(
        op.f('ix_account_information_last_name'),
        table_name='account_information'
    )
    op.drop_column('account_information', 'last_name')

    # Remove first_name column and index
    op.drop_index(
        op.f('ix_account_information_first_name'),
        table_name='account_information'
    )
    op.drop_column('account_information', 'first_name')

    # Drop account_status enum type
    op.execute('DROP TYPE IF EXISTS account_status')
