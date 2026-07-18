"""add tasks.deadline

Revision ID: 6747dc8a671d
Revises: 64f66ba5c04d
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6747dc8a671d'
down_revision: Union[str, Sequence[str], None] = '64f66ba5c04d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, no default needed — existing rows simply have no deadline set.
    op.add_column('tasks', sa.Column('deadline', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'deadline')
