"""Per-type reminder switches. Each defaults off.

Revision ID: reminder_types_off
Revises: reminder_switch_off
Create Date: 2026-11-07 18:25:00

Adds three columns to the table from ``reminder_switch_off``. It does not
change that earlier revision. Live databases still on ``0006_sprint7`` reach
this head by applying ``reminder_switch_off`` first, then this file. A database
that already has the three-column PR 31 table gains the columns here.

``create_all`` creates a missing ``reminder_control`` table. It does not add
columns to a table that already exists. If that older table is present, run
this revision before expecting the type switches to be stored.

Downgrade drops only these three columns. The master ``enabled`` value stays.
A waiting reminder card is not deleted. Do not run this on the live database
until that change is approved, and take a backup first.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "reminder_types_off"
down_revision: Union[str, None] = "reminder_switch_off"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("overdue", "stalled", "upcoming")


def upgrade() -> None:
    for name in _COLUMNS:
        op.execute(
            f"ALTER TABLE reminder_control ADD COLUMN IF NOT EXISTS {name} "
            "BOOLEAN NOT NULL DEFAULT false"
        )


def downgrade() -> None:
    for name in _COLUMNS:
        op.execute(f"ALTER TABLE reminder_control DROP COLUMN IF EXISTS {name}")
