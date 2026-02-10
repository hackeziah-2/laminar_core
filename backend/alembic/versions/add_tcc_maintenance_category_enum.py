"""add category (tcc_category_enum) to tcc_maintenance

Revision ID: add_tcc_category_enum
Revises: rename_setting_tcc_to_tcc
Create Date: 2026-02-10

Adds tcc_category_enum (Powerplant, Airframe, Inspection Servicing) and category column to tcc_maintenance.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "add_tcc_category_enum"
down_revision: Union[str, Sequence[str], None] = "create_setting_tcc_maintenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type (checkfirst so no error if already exists)
    tcc_category_enum_create = postgresql.ENUM(
        "Powerplant",
        "Airframe",
        "Inspection Servicing",
        name="tcc_category_enum",
        create_type=True,
    )
    tcc_category_enum_create.create(op.get_bind(), checkfirst=True)

    # Add category column using the type (create_type=False for table)
    tcc_category_enum = postgresql.ENUM(
        "Powerplant",
        "Airframe",
        "Inspection Servicing",
        name="tcc_category_enum",
        create_type=False,
    )
    op.add_column(
        "tcc_maintenance",
        sa.Column("category", tcc_category_enum, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tcc_maintenance", "category")
    tcc_category_enum = postgresql.ENUM(
        name="tcc_category_enum", create_type=False
    )
    tcc_category_enum.drop(op.get_bind(), checkfirst=True)
