"""add task skills and refreshable student career recommendations

Revision ID: 7c8e91f24a10
Revises: d156edf3f99f
Create Date: 2026-07-18 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c8e91f24a10"
down_revision: Union[str, Sequence[str], None] = "d156edf3f99f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_skills",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("task_id", "skill_id"),
    )

    op.add_column(
        "student_career_recommendations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Older versions appended every generated batch. Keep the newest row per
    # student/career before enforcing update-in-place semantics.
    op.execute(
        """
        DELETE FROM student_career_recommendations older
        USING student_career_recommendations newer
        WHERE older.student_id = newer.student_id
          AND older.career_id = newer.career_id
          AND (
            older.created_at < newer.created_at
            OR (older.created_at = newer.created_at AND older.id < newer.id)
          )
        """
    )
    op.create_unique_constraint(
        "uq_student_career_recommendation",
        "student_career_recommendations",
        ["student_id", "career_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_student_career_recommendation",
        "student_career_recommendations",
        type_="unique",
    )
    op.drop_column("student_career_recommendations", "updated_at")
    op.drop_table("task_skills")
