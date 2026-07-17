from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
import enum

class TaskDifficulty(enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"

class TaskInputType(enum.Enum):
    DATASET = "DATASET"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"

class SubmissionStatus(enum.Enum):
    JOINED = "JOINED"
    SUBMITTED = "SUBMITTED"
    AUTO_CHECK_PASSED = "AUTO_CHECK_PASSED"
    AUTO_CHECK_FAILED = "AUTO_CHECK_FAILED"
    MENTOR_APPROVED = "MENTOR_APPROVED"
    MENTOR_REJECTED = "MENTOR_REJECTED"
    COMPLETED = "COMPLETED"

# Shared by TaskSubmission.completed_by and TaskSubmissionScore.scored_by —
# both answer the same question ("which kind of actor performed this step").
class CompletionActor(enum.Enum):
    AI = "AI"
    MENTOR = "MENTOR"

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    difficulty: Mapped[TaskDifficulty] = mapped_column(SQLEnum(TaskDifficulty))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    # Null = root/standalone task. Set = this row is a sub-task of another Task.
    # The referenced parent must itself have parent_task_id=None — enforced in
    # the service layer (max depth 2), not here, since a DB CHECK constraint
    # can't see other rows.
    parent_task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    estimated_hours_min: Mapped[int] = mapped_column(Integer)
    estimated_hours_max: Mapped[int] = mapped_column(Integer)
    # Null when this task has sub-tasks: points are then computed by summing
    # points_awarded across the sub-tasks' own completed submissions instead
    # (see TaskService.get_task_progress) rather than being a static catalog value.
    competency_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    context: Mapped[str] = mapped_column(String(4000))
    scope_included: Mapped[list] = mapped_column(JSON, default=list)
    scope_excluded: Mapped[list] = mapped_column(JSON, default=list)
    requires_auto_check: Mapped[bool] = mapped_column(default=False)
    requires_mentor_approval: Mapped[bool] = mapped_column(default=True)
    mentor_approval_sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_privacy_notice: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    company = relationship("Company")
    # remote_side=[id] tells SQLAlchemy which side of the self-join is the "one"
    # (the parent); backref="sub_tasks" gives every Task a `.sub_tasks` list.
    parent_task = relationship("Task", remote_side=[id], backref="sub_tasks")
    inputs = relationship("TaskInput", back_populates="task", cascade="all, delete-orphan")
    outputs = relationship("TaskOutput", back_populates="task", cascade="all, delete-orphan")
    criteria = relationship("TaskEvaluationCriterion", back_populates="task", cascade="all, delete-orphan")

class TaskInput(Base):
    __tablename__ = "task_inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    input_type: Mapped[TaskInputType] = mapped_column(SQLEnum(TaskInputType), default=TaskInputType.OTHER)
    # UI shows a lock icon on some inputs — read as "only released once the
    # student has joined the task", not enforced here (no file storage yet).
    is_restricted: Mapped[bool] = mapped_column(default=False)

    task = relationship("Task", back_populates="inputs")

class TaskOutput(Base):
    __tablename__ = "task_outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    sort_order: Mapped[int] = mapped_column(default=0)
    description: Mapped[str] = mapped_column(String(1000))

    task = relationship("Task", back_populates="outputs")

class TaskEvaluationCriterion(Base):
    __tablename__ = "task_evaluation_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    criterion: Mapped[str] = mapped_column(String(500))
    # Criteria for the same task should sum to 100 — a business rule validated
    # in the service layer (a DB CHECK can't sum across sibling rows either).
    weight_percent: Mapped[int] = mapped_column(Integer)

    task = relationship("Task", back_populates="criteria")

class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    # Not a FK: Student is hosted in a separate service. This is a plain
    # indexed integer the caller supplies, never joined against in this DB.
    student_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[SubmissionStatus] = mapped_column(SQLEnum(SubmissionStatus), default=SubmissionStatus.JOINED)
    joined_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    report_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    auto_check_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    mentor_feedback: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    mentor_decision_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_by: Mapped[Optional[CompletionActor]] = mapped_column(SQLEnum(CompletionActor), nullable=True)
    # Snapshot of Task.competency_points at the moment of completion — never
    # re-read from Task later, so a later change to the task's point value
    # doesn't retroactively rewrite history for students who already finished.
    points_awarded: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    task = relationship("Task")
    scores = relationship("TaskSubmissionScore", back_populates="submission", cascade="all, delete-orphan")

class TaskSubmissionScore(Base):
    """Actual per-criterion grading for one submission. TaskEvaluationCriterion
    is just the rubric (criteria + weight for the Task); this table is where a
    specific submission's result against each criterion is recorded."""
    __tablename__ = "task_submission_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("task_submissions.id"))
    criterion_id: Mapped[int] = mapped_column(ForeignKey("task_evaluation_criteria.id"))
    score_percent: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    scored_by: Mapped[CompletionActor] = mapped_column(SQLEnum(CompletionActor))
    scored_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    submission = relationship("TaskSubmission", back_populates="scores")
    criterion = relationship("TaskEvaluationCriterion")
