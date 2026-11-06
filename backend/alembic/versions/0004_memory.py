"""Household memory and the pgvector extension.

Revision ID: 0004_memory
Revises: 0003_sprint3
Create Date: 2026-11-06 06:40:00

Upgrade after a backup, and only once the database can load pgvector.
The statements are idempotent, so a process that already applied the boot
patch can still move the Alembic version forward.

Downgrade deletes remember and forget cards, drops memory_items, and removes
the vector extension from this database. It does not restore the rows.
"""

from typing import Sequence, Union

from alembic import op

from organiser.patches import MEMORY_DOWNGRADE, MEMORY_UPGRADE

revision: str = "0004_memory"
down_revision: Union[str, None] = "0003_sprint3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in MEMORY_UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in MEMORY_DOWNGRADE:
        op.execute(statement)
