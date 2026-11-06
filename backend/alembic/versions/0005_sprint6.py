"""Alert dismissals.

Revision ID: 0005_sprint6
Revises: 0004_memory
Create Date: 2026-11-06 12:40:00

Upgrade after a backup. The statements are idempotent, so a process that
already applied the boot patch can still move the Alembic version forward.

Downgrade drops the dismissals. It does not send anything, and it does not
restore the hidden cards. The cards are computed, so they come back on their own.
"""

from typing import Sequence, Union

from alembic import op

from organiser.patches import ALERT_DOWNGRADE, ALERT_UPGRADE

revision: str = "0005_sprint6"
down_revision: Union[str, None] = "0004_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in ALERT_UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in ALERT_DOWNGRADE:
        op.execute(statement)
