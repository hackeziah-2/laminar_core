"""use REGULATORY_CORRESPONDENCE_NON_CERT as category_type value

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-03-16

Adds enum value REGULATORY_CORRESPONDENCE_NON_CERT and migrates rows from
'REGULATORY CORRESPONDENCE (NON CERT)' to it. The old value remains in the
enum type (PostgreSQL does not support removing enum values easily).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum value (for DBs that were created with the old value).
    # Must run in autocommit so the new value is visible before the UPDATE (PostgreSQL requirement).
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE oem_technical_publication_category_type ADD VALUE IF NOT EXISTS 'REGULATORY_CORRESPONDENCE_NON_CERT'"
        )
    # Migrate existing data from old value to new value
    op.execute(
        """
        UPDATE oem_technical_publications
        SET category_type = 'REGULATORY_CORRESPONDENCE_NON_CERT'::oem_technical_publication_category_type
        WHERE category_type::text = 'REGULATORY CORRESPONDENCE (NON CERT)'
        """
    )


def downgrade() -> None:
    # Revert data back to old value (if we had stored it)
    op.execute(
        """
        UPDATE oem_technical_publications
        SET category_type = 'REGULATORY CORRESPONDENCE (NON CERT)'::oem_technical_publication_category_type
        WHERE category_type::text = 'REGULATORY_CORRESPONDENCE_NON_CERT'
        """
    )
    # Note: we do not remove the enum value 'REGULATORY_CORRESPONDENCE_NON_CERT' from the type
    # (PostgreSQL does not support removing enum values).
