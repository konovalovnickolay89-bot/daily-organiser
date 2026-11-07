"""House switch for local reminder cards. Off by default.

Revision ID: reminder_switch_off
Revises: 0006_sprint7
Create Date: 2026-11-07 15:45:00

This is not ``0007_settings_search`` and not ``0007_x_poll_pause``. Those two
open revisions both sit on ``0006_sprint7``. This file is a separate head.
Do not run it against the live database from this change. Take a backup first,
and reconcile the two ``0007`` revisions before ``upgrade heads``.

Downgrade drops only this switch. It does not delete tasks, memories, or posts.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "reminder_switch_off"
down_revision: Union[str, None] = "0006_sprint7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reminder_control (
            id INTEGER PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT false,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_reminder_control_singleton CHECK (id = 1)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reminder_control")
