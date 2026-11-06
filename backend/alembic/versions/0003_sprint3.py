"""Commute shifts, and the catch-up fallback marker.

Revision ID: 0003_sprint3
Revises: 0002_sprint2
Create Date: 2026-11-06 05:10:00

Upgrade after a backup. The statements are idempotent, so a process that
already applied the boot patch can still move the Alembic version forward.
"""

from typing import Sequence, Union

from alembic import op

from organiser.patches import SPRINT3_DOWNGRADE, SPRINT3_UPGRADE

revision: str = "0003_sprint3"
down_revision: Union[str, None] = "0002_sprint2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in SPRINT3_UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in SPRINT3_DOWNGRADE:
        op.execute(statement)
