"""add nature_of_flight_description table

Revision ID: cc2dd3ee4ff5
Revises: bb1cc2dd3ee4
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "cc2dd3ee4ff5"
down_revision: Union[str, Sequence[str], None] = "bb1cc2dd3ee4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    nature_of_flight_enum = postgresql.ENUM(
        "TR",
        "PSF",
        "PRF",
        "EGR",
        "ME",
        "TR_WITH_PIREM",
        "VOID",
        "ATL_REPL",
        "CANCELLED_FLT",
        name="nature_of_flight",
        create_type=False,
    )
    op.create_table(
        "nature_of_flight_description",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aircraft_fk", sa.Integer(), nullable=False),
        sa.Column("nature_of_flight", nature_of_flight_enum, nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["aircraft_fk"], ["aircrafts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["account_information.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["account_information.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_nature_of_flight_description_id"),
        "nature_of_flight_description",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nature_of_flight_description_aircraft_fk"),
        "nature_of_flight_description",
        ["aircraft_fk"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nature_of_flight_description_nature_of_flight"),
        "nature_of_flight_description",
        ["nature_of_flight"],
        unique=False,
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_nature_of_flight_description_aircraft_nof_active
        ON nature_of_flight_description (aircraft_fk, nature_of_flight)
        WHERE is_deleted IS FALSE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_nature_of_flight_description_aircraft_nof_active")
    op.drop_index(
        op.f("ix_nature_of_flight_description_nature_of_flight"),
        table_name="nature_of_flight_description",
    )
    op.drop_index(
        op.f("ix_nature_of_flight_description_aircraft_fk"),
        table_name="nature_of_flight_description",
    )
    op.drop_index(
        op.f("ix_nature_of_flight_description_id"),
        table_name="nature_of_flight_description",
    )
    op.drop_table("nature_of_flight_description")
