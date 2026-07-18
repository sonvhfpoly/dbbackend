"""add tasks.updated_at and tasks.deadline

The shared Neon dev DB already has both columns (added directly, out-of-band,
presumably for an in-progress deadline feature) — discovered because task
creation was failing there with "null value in column updated_at violates
not-null constraint" once the model didn't set it. This migration brings the
model/tracked schema in line with what's already live, same situation as
d156edf3f99f before it. Since Neon already has these columns, this migration
should be stamped there rather than executed — only run `alembic upgrade`
for real on a fresh DB that doesn't have them yet.

Revision ID: 7f146e36e9fd
Revises: e3b7c95229e3
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f146e36e9fd'
down_revision: Union[str, Sequence[str], None] = 'e3b7c95229e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default lets existing rows backfill during the ADD COLUMN, same
    # convention as d156edf3f99f's complexity_level/risk_level/etc columns.
    op.add_column('tasks', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.alter_column('tasks', 'updated_at', server_default=None)
    op.add_column('tasks', sa.Column('deadline', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'deadline')
    op.drop_column('tasks', 'updated_at')
