"""add task_skills, drop student_skill

StudentSkill (student_skill table) was a binary student<->skill tag with no
level/confidence/evidence, written only by demo seeding and never read by any
real skill-consuming service (StudentSkillProfile — verified via the
EvidenceClaim pipeline — is the sole source of truth everywhere else). It's
replaced entirely rather than just stopping writes to it. TaskSkill is new:
it lets a Task declare which skill(s) it builds (populated by AI right after
task creation), so completing a submission can auto-draft an EvidenceClaim
for the right skill(s) instead of requiring someone to link it by hand.

Revision ID: e3b7c95229e3
Revises: d156edf3f99f
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3b7c95229e3'
down_revision: Union[str, Sequence[str], None] = 'd156edf3f99f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'task_skills',
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.PrimaryKeyConstraint('task_id', 'skill_id'),
    )
    op.drop_table('student_skill')


def downgrade() -> None:
    op.create_table(
        'student_skill',
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('student_id', 'skill_id'),
    )
    op.drop_table('task_skills')
