"""add task_inputs.storage_url

Revision ID: bd032da8d4b7
Revises: 5c5ad1ae4890
Create Date: 2026-07-19 08:45:15.836126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd032da8d4b7'
down_revision: Union[str, Sequence[str], None] = '5c5ad1ae4890'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, no default needed — existing inputs simply have no attached file.
    op.add_column('task_inputs', sa.Column('storage_url', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column('task_inputs', 'storage_url')
