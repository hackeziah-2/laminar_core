"""drop reg_no from aircraft

Revision ID: bc15bce97066
Revises: 874e1ec27475
Create Date: 2025-12-10 10:56:10.077907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc15bce97066'
down_revision: Union[str, Sequence[str], None] = '874e1ec27475'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('aircrafts', 'reg_no')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('aircrafts', sa.Column('reg_no', sa.String(), nullable=True))
