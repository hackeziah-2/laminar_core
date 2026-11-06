"""allow a blank LDND unit

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-11-05

Annual inspections do not use HRS or CYCLES, so unit may be null.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, Sequence[str], None] = "i0j1k2l3m4n5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "ldnd_monitoring",
        "unit",
        existing_type=postgresql.ENUM("HRS", "CYCLES", name="ldnd_unit", create_type=False),
        nullable=True,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE ldnd_monitoring SET unit = 'HRS'::ldnd_unit WHERE unit IS NULL"
    )
    op.alter_column(
        "ldnd_monitoring",
        "unit",
        existing_type=postgresql.ENUM("HRS", "CYCLES", name="ldnd_unit", create_type=False),
        nullable=False,
        existing_nullable=True,
    )
