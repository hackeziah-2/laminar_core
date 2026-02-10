"""drop part_description from component_record tables

Revision ID: drop_part_desc_component
Revises: add_component_record
Create Date: 2026-02-06

Drops part_description from engine_component_record, airframe_component_record, avionics_component_record.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "drop_part_desc_component"
down_revision: Union[str, Sequence[str], None] = "add_component_record"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE engine_component_record DROP COLUMN IF EXISTS part_description")
    op.execute("ALTER TABLE airframe_component_record DROP COLUMN IF EXISTS part_description")
    op.execute("ALTER TABLE avionics_component_record DROP COLUMN IF EXISTS part_description")


def downgrade() -> None:
    op.execute("ALTER TABLE engine_component_record ADD COLUMN part_description TEXT")
    op.execute("ALTER TABLE airframe_component_record ADD COLUMN part_description TEXT")
    op.execute("ALTER TABLE avionics_component_record ADD COLUMN part_description TEXT")
