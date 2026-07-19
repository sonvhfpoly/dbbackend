"""add enterprise_reviews

Revision ID: e3f9a1c2b5d7
Revises: bd032da8d4b7
Create Date: 2026-07-19 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f9a1c2b5d7'
down_revision: Union[str, Sequence[str], None] = 'bd032da8d4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'enterprise_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=False),
        sa.Column('decision', sa.Enum('ACCEPTED', 'CHANGES_REQUESTED', name='enterprisereviewdecision'), nullable=False),
        sa.Column('comment', sa.String(length=2000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['task_submissions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('enterprise_reviews')
    sa.Enum(name='enterprisereviewdecision').drop(op.get_bind(), checkfirst=True)
