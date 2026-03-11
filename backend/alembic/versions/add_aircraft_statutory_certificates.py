"""add aircraft_statutory_certificates table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY_VALUES = (
    "COA", "COR", "NTC", "PITOT_STATIC", "TRANSPONDER", "ELT",
    "WEIGHT_BALANCE", "COMPASS_SWING", "MARKING_RESERVATION",
    "BINARY_CODE_24BIT", "IBRD_CORPAS",
)


def upgrade() -> None:
    category_enum = postgresql.ENUM(
        *CATEGORY_VALUES,
        name="statutory_certificate_category_type",
        create_type=True,
    )
    category_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "aircraft_statutory_certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aircraft_fk", sa.Integer(), nullable=False),
        sa.Column(
            "category_type",
            postgresql.ENUM(
                *CATEGORY_VALUES,
                name="statutory_certificate_category_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("date_of_expiration", sa.Date(), nullable=True),
        sa.Column("web_link", sa.String(length=2048), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
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
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["aircraft_fk"], ["aircrafts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_aircraft_statutory_certificates_id"),
        "aircraft_statutory_certificates",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_aircraft_statutory_certificates_aircraft_fk"),
        "aircraft_statutory_certificates",
        ["aircraft_fk"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_aircraft_statutory_certificates_aircraft_fk"),
        table_name="aircraft_statutory_certificates",
    )
    op.drop_index(
        op.f("ix_aircraft_statutory_certificates_id"),
        table_name="aircraft_statutory_certificates",
    )
    op.drop_table("aircraft_statutory_certificates")
    op.execute("DROP TYPE IF EXISTS statutory_certificate_category_type")
