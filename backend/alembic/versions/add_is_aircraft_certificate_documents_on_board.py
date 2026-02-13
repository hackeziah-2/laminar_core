"""add is_aircraft_certificate to documents_on_board

Revision ID: add_is_aircraft_certificate_dob
Revises: 6f31c231f9f6
Create Date: 2026-02-10

Adds is_aircraft_certificate boolean column (default False) to documents_on_board.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_is_aircraft_certificate_dob"
down_revision: Union[str, Sequence[str], None] = "6f31c231f9f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents_on_board",
        sa.Column("is_aircraft_certificate", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("documents_on_board", "is_aircraft_certificate")
