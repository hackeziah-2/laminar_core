"""add web_link to documents_on_board

Revision ID: 6f31c231f9f6
Revises: make_tcc_atl_ref_nullable
Create Date: 2026-02-11 04:33:01.978736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f31c231f9f6'
down_revision: Union[str, Sequence[str], None] = 'make_tcc_atl_ref_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents_on_board',
        sa.Column('web_link', sa.String(length=2048), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('documents_on_board', 'web_link')

