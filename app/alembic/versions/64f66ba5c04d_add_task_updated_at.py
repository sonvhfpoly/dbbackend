"""add tasks.updated_at

Revision ID: 64f66ba5c04d
Revises: d156edf3f99f
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64f66ba5c04d'
down_revision: Union[str, Sequence[str], None] = 'd156edf3f99f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default backfills existing rows during the ADD COLUMN; dropped
    # afterward since the model only defines a Python-side default/onupdate,
    # not a DB-level one (same pattern as migration d156edf3f99f).
    op.add_column('tasks', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.alter_column('tasks', 'updated_at', server_default=None)


def downgrade() -> None:
    op.drop_column('tasks', 'updated_at')
