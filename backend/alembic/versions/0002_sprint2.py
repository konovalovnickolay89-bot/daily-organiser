"""Shopping, diary subscriptions, integration status, assistant switch.

Revision ID: 0002_sprint2
Revises: 0001_baseline
Create Date: 2026-11-06 04:40:00

Upgrade after a backup. The statements are idempotent, so a process that
already applied the boot patch can still move the Alembic version forward.
"""

from typing import Sequence, Union

from alembic import op

from organiser.patches import SPRINT2_DOWNGRADE, SPRINT2_UPGRADE

revision: str = "0002_sprint2"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in SPRINT2_UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in SPRINT2_DOWNGRADE:
        op.execute(statement)
