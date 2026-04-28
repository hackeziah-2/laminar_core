"""merge d3e4 and a4b5 heads

Revision ID: 7dc267d99fde
Revises: d3e4f5a6b7c8, a4b5c6d7e8f9
Create Date: 2026-04-27 03:36:17.069419

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7dc267d99fde'
down_revision: Union[str, Sequence[str], None] = ('d3e4f5a6b7c8', 'a4b5c6d7e8f9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
