"""make aircraft_fk nullable in documents_on_board

Revision ID: ec9a64edc639
Revises: 3b77e8d59325
Create Date: 2026-02-16 04:51:03.659787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ec9a64edc639'
down_revision: Union[str, Sequence[str], None] = '3b77e8d59325'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('documents_on_board', 'aircraft_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('documents_on_board', 'aircraft_id',
               existing_type=sa.INTEGER(),
               nullable=False)
