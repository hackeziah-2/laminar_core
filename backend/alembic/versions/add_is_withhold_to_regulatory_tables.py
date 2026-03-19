"""add is_withhold (boolean, default false) to aircraft_statutory_certificates, organizational_approvals, oem_technical_publications, personnel_authorization

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-03-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aircraft_statutory_certificates",
        sa.Column("is_withhold", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "organizational_approvals",
        sa.Column("is_withhold", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "oem_technical_publications",
        sa.Column("is_withhold", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "personnel_authorization",
        sa.Column("is_withhold", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("aircraft_statutory_certificates", "is_withhold")
    op.drop_column("organizational_approvals", "is_withhold")
    op.drop_column("oem_technical_publications", "is_withhold")
    op.drop_column("personnel_authorization", "is_withhold")
