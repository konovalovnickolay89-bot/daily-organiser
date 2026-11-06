"""X connection, watches, items, and the post audit.

Revision ID: 0006_sprint7
Revises: 0005_sprint6
Create Date: 2026-11-06 13:40:00

Upgrade after a backup. The statements are idempotent, so a process that
already applied the boot patch can still move the Alembic version forward.

Downgrade drops the X rows. A post that already went out stays on X.
Refresh tokens in this database are deleted with the connection row.
"""

from typing import Sequence, Union

from alembic import op

from organiser.patches import SPRINT7_DOWNGRADE, SPRINT7_UPGRADE

revision: str = "0006_sprint7"
down_revision: Union[str, None] = "0005_sprint6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in SPRINT7_UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in SPRINT7_DOWNGRADE:
        op.execute(statement)
