"""add aircraft_history table

Revision ID: e2f3a4b5c6d7
Revises: d2e3f4a5b6c7
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aircraft_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aircraft_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["aircraft_id"], ["aircrafts.id"]),
        sa.ForeignKeyConstraint(["changed_by"], ["account_information.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_aircraft_history_id"), "aircraft_history", ["id"], unique=False)
    op.create_index(
        op.f("ix_aircraft_history_aircraft_id"),
        "aircraft_history",
        ["aircraft_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_aircraft_history_field_name"),
        "aircraft_history",
        ["field_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_aircraft_history_changed_by"),
        "aircraft_history",
        ["changed_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_aircraft_history_action_type"),
        "aircraft_history",
        ["action_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_aircraft_history_action_type"), table_name="aircraft_history")
    op.drop_index(op.f("ix_aircraft_history_changed_by"), table_name="aircraft_history")
    op.drop_index(op.f("ix_aircraft_history_field_name"), table_name="aircraft_history")
    op.drop_index(op.f("ix_aircraft_history_aircraft_id"), table_name="aircraft_history")
    op.drop_index(op.f("ix_aircraft_history_id"), table_name="aircraft_history")
    op.drop_table("aircraft_history")
