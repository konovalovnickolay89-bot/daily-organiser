"""Pause flag for X reading.

Revision ID: 0007_x_poll_pause
Revises: 0006_sprint7
Create Date: 2026-11-07 02:30:00

Adds ``x_meter.poll_paused``. It stops bookmark and watch reads.
It does not post, and it is not the house pause. Downgrade drops the flag only.
"""

from typing import Sequence, Union

from alembic import op

from organiser.patches import X_POLL_PAUSE_DOWNGRADE, X_POLL_PAUSE_UPGRADE

revision: str = "0007_x_poll_pause"
down_revision: Union[str, None] = "0006_sprint7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in X_POLL_PAUSE_UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in X_POLL_PAUSE_DOWNGRADE:
        op.execute(statement)
