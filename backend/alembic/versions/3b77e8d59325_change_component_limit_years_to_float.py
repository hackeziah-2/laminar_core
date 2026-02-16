"""change component_limit_years to float

Revision ID: 3b77e8d59325
Revises: add_is_aircraft_certificate_dob
Create Date: 2026-02-16 03:26:45.097316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3b77e8d59325'
down_revision: Union[str, Sequence[str], None] = 'add_is_aircraft_certificate_dob'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('tcc_maintenance', 'component_limit_years',
               existing_type=sa.INTEGER(),
               type_=sa.Float(),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('tcc_maintenance', 'component_limit_years',
               existing_type=sa.Float(),
               type_=sa.INTEGER(),
               existing_nullable=True)
