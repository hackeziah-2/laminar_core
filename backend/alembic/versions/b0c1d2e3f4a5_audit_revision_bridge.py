"""Bridge revision: databases were stamped with this id during development.

Revision ID: b0c1d2e3f4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-03-27

Alembic requires every version_num in alembic_version to exist as a script.
This revision is a no-op; the substantive migration is c1d2e3f4a5b6
(add_audit_columns_all_tables).

If your database already has created_by/updated_by from a manual or partial run,
stamp head instead of upgrading:

    alembic stamp c1d2e3f4a5b6

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
