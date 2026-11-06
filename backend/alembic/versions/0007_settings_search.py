"""House settings and full-text search on memory.

Revision ID: 0007_settings_search
Revises: 0006_sprint7
Create Date: 2026-11-06 16:40:00

Upgrade after a backup. The statements are idempotent, so a process that
already applied the boot patch can still move the Alembic version forward.

``search_vector`` is maintained by a trigger. ``to_tsvector`` is not immutable,
so it is not a generated column. Downgrade drops the column, the index, and
``house_settings``. Memories themselves stay until ``0004_memory`` is rolled back.
"""

from typing import Sequence, Union

from alembic import op

from organiser.patches import SETTINGS_DOWNGRADE, SETTINGS_UPGRADE

revision: str = "0007_settings_search"
down_revision: Union[str, None] = "0006_sprint7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in SETTINGS_UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in SETTINGS_DOWNGRADE:
        op.execute(statement)
