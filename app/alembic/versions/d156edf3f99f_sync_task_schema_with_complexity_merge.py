"""sync tasks/task_submissions columns with the difficulty->complexity_level merge

The Neon DB was never migrated past the pre-simplification schema (it was
stamped at an orphaned revision from before the baseline squash), so
`tasks` still has the old `difficulty` column instead of
complexity_level/risk_level/target_evidence_level/review_status/checkpoints,
and `task_submissions` is missing student_reflection/elapsed_seconds. This
brings both tables in line with the current models/baseline schema.

Revision ID: d156edf3f99f
Revises: ba680aca4f7b
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd156edf3f99f'
down_revision: Union[str, Sequence[str], None] = 'ba680aca4f7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The four enum types already exist in this DB (created alongside
    # task_reviews/evidence_claims after those domains were added post-baseline),
    # so create_type=False avoids a duplicate "CREATE TYPE" error.
    complexity_enum = postgresql.ENUM('T1', 'T2', 'T3', name='taskcomplexity', create_type=False)
    risk_enum = postgresql.ENUM('R0', 'R1', 'R2', 'R3', name='taskrisklevel', create_type=False)
    evidence_enum = postgresql.ENUM('L1', 'L2', 'L3', 'L4', 'L5', name='evidencelevel', create_type=False)
    review_enum = postgresql.ENUM(
        'PENDING_MENTOR_APPROVAL', 'APPROVED', 'REJECTED', 'NEED_MORE_INFO',
        name='taskreviewstatus', create_type=False,
    )

    # server_default lets existing rows backfill during the ADD COLUMN; dropped
    # afterward since the model only defines a Python-side default, not a DB one.
    op.add_column('tasks', sa.Column('complexity_level', complexity_enum, nullable=False, server_default='T1'))
    op.add_column('tasks', sa.Column('risk_level', risk_enum, nullable=False, server_default='R0'))
    op.add_column('tasks', sa.Column('target_evidence_level', evidence_enum, nullable=False, server_default='L1'))
    op.add_column('tasks', sa.Column('review_status', review_enum, nullable=False, server_default='PENDING_MENTOR_APPROVAL'))
    op.add_column('tasks', sa.Column('checkpoints', sa.JSON(), nullable=False, server_default='[]'))
    op.drop_column('tasks', 'difficulty')

    op.alter_column('tasks', 'complexity_level', server_default=None)
    op.alter_column('tasks', 'risk_level', server_default=None)
    op.alter_column('tasks', 'target_evidence_level', server_default=None)
    op.alter_column('tasks', 'review_status', server_default=None)
    op.alter_column('tasks', 'checkpoints', server_default=None)

    op.execute('DROP TYPE IF EXISTS taskdifficulty')

    op.add_column('task_submissions', sa.Column('student_reflection', sa.JSON(), nullable=True))
    op.add_column('task_submissions', sa.Column('elapsed_seconds', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('task_submissions', 'elapsed_seconds')
    op.drop_column('task_submissions', 'student_reflection')

    op.execute("CREATE TYPE taskdifficulty AS ENUM ('EASY', 'MEDIUM', 'HARD')")
    op.add_column('tasks', sa.Column('difficulty', postgresql.ENUM('EASY', 'MEDIUM', 'HARD', name='taskdifficulty', create_type=False), nullable=True))
    op.drop_column('tasks', 'checkpoints')
    op.drop_column('tasks', 'review_status')
    op.drop_column('tasks', 'target_evidence_level')
    op.drop_column('tasks', 'risk_level')
    op.drop_column('tasks', 'complexity_level')
