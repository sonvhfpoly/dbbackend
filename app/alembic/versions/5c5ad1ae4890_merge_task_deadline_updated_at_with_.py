"""merge task deadline/updated_at with task skills and recommendations

Revision ID: 5c5ad1ae4890
Revises: 6747dc8a671d, 7c8e91f24a10
Create Date: 2026-07-18 21:26:50.201504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c5ad1ae4890'
down_revision: Union[str, Sequence[str], None] = ('6747dc8a671d', '7c8e91f24a10')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
