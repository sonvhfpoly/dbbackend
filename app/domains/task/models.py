from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
import enum

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

# Task complexity ("T-level" in the product spec). T4/T5 are intentionally
# absent: they're out of scope for MVP, so the type system itself blocks them
# rather than relying on a runtime check.
class TaskComplexity(enum.Enum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"

# Task data-risk ("R-level"). R2/R3 exist here (unlike TaskComplexity's T4/T5)
# because the spec's rule is a runtime gate — "risk_level >= R2 blocks
# APPROVED" — not an MVP type-level exclusion; see TaskService.review_task.
class TaskRiskLevel(enum.Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"

# Target/observed student skill level ("Evidence Level" / Skill Level in the
# spec). Used both as Task.target_evidence_level and as
# EvidenceClaim.proposed_skill_level in the evidence domain.
class EvidenceLevel(enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"

# Mentor decision on a Task itself (distinct from TaskSubmission review,
# which judges a student's work). PENDING_MENTOR_APPROVAL is the initial
# state; NEED_MORE_INFO loops back to it after the business clarifies.
class TaskReviewStatus(enum.Enum):
    PENDING_MENTOR_APPROVAL = "PENDING_MENTOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEED_MORE_INFO = "NEED_MORE_INFO"

class FileScanStatus(enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"

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
    # Business's desired completion date (requirements.md §7.1 Business Input's
    # `deadline`) — optional, display/planning only, no backend gate enforces
    # it (distinct from a per-assignment due_at, which this MVP doesn't have).
    deadline: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    # Milestones a student is expected to hit while working outside WORKLAB
    # (requirements.md §7.2's AI Structured Task Output) — display-only, no
    # backend gate is tied to them (no Work Session/progress tracking in MVP).
    checkpoints: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    # Bumped automatically whenever this row is updated (mentor review
    # overriding complexity/risk, AI planning setting complexity_level) — no
    # extra code needed at the call sites, SQLAlchemy sets it on flush.
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # T-level / R-level / target skill level as proposed by the business or AI
    # at creation time; a mentor review (see TaskReview below) can override
    # complexity_level/risk_level/target_evidence_level with its own values.
    complexity_level: Mapped[TaskComplexity] = mapped_column(SQLEnum(TaskComplexity), default=TaskComplexity.T1)
    risk_level: Mapped[TaskRiskLevel] = mapped_column(SQLEnum(TaskRiskLevel), default=TaskRiskLevel.R0)
    target_evidence_level: Mapped[EvidenceLevel] = mapped_column(SQLEnum(EvidenceLevel), default=EvidenceLevel.L1)
    # A task can't be joined by a student until this is APPROVED — see
    # TaskService.review_task / join_task.
    review_status: Mapped[TaskReviewStatus] = mapped_column(
        SQLEnum(TaskReviewStatus), default=TaskReviewStatus.PENDING_MENTOR_APPROVAL
    )

    company = relationship("Company")
    # remote_side=[id] tells SQLAlchemy which side of the self-join is the "one"
    # (the parent); backref="sub_tasks" gives every Task a `.sub_tasks` list.
    parent_task = relationship("Task", remote_side=[id], backref="sub_tasks")
    inputs = relationship("TaskInput", back_populates="task", cascade="all, delete-orphan")
    outputs = relationship("TaskOutput", back_populates="task", cascade="all, delete-orphan")
    criteria = relationship("TaskEvaluationCriterion", back_populates="task", cascade="all, delete-orphan")
    reviews = relationship("TaskReview", back_populates="task", cascade="all, delete-orphan")
    skills = relationship("Skill", secondary="task_skills")

class TaskSkill(Base):
    """Curated skills exercised by a task.

    This is deliberately separate from EvidenceClaim: task skills describe
    what the task exercises, while evidence describes what a reviewer has
    actually verified for one student's submission.
    """
    __tablename__ = "task_skills"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)

class TaskInput(Base):
    __tablename__ = "task_inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    input_type: Mapped[TaskInputType] = mapped_column(SQLEnum(TaskInputType), default=TaskInputType.OTHER)
    # UI shows a lock icon on some inputs — read as "only released once the
    # student has joined the task", not enforced here.
    is_restricted: Mapped[bool] = mapped_column(default=False)
    # Public GCS URL when this input is a real file — populated automatically
    # for inputs TaskBuilderService.generate_task copies over from the
    # conversation's uploaded documents (see domains/task_builder/storage.py);
    # null for inputs that are just a name/description with no attached file
    # (e.g. a manually-created task's business-authored inputs).
    storage_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

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

class TaskReview(Base):
    """One mentor decision on a Task itself — approve/reject/request-more-info
    before students can join it. A task can be reviewed more than once (e.g.
    NEED_MORE_INFO -> business updates -> re-review), so this is an append-only
    history rather than a single row updated in place; Task.review_status
    always reflects the latest decision."""
    __tablename__ = "task_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    # Not a FK: there's no Mentor/User identity table yet in this MVP, same
    # convention as TaskSubmission.student_id below.
    reviewer_id: Mapped[int] = mapped_column(Integer, index=True)
    decision: Mapped[TaskReviewStatus] = mapped_column(SQLEnum(TaskReviewStatus))
    approved_complexity: Mapped[Optional[TaskComplexity]] = mapped_column(SQLEnum(TaskComplexity), nullable=True)
    approved_risk: Mapped[Optional[TaskRiskLevel]] = mapped_column(SQLEnum(TaskRiskLevel), nullable=True)
    approved_evidence_level: Mapped[Optional[EvidenceLevel]] = mapped_column(SQLEnum(EvidenceLevel), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    task = relationship("Task", back_populates="reviews")

class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    # Not a FK: Student is hosted in a separate service. This is a plain
    # indexed integer the caller supplies, never joined against in this DB.
    student_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[SubmissionStatus] = mapped_column(SQLEnum(SubmissionStatus), default=SubmissionStatus.JOINED)
    # joined_at doubles as this MVP's "accepted_at" (requirements.md §12/§13):
    # there's no separate assign->accept step, joining a task IS accepting it.
    joined_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    report_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    # requirements.md §12: only ever surfaced as a rounded "N days M hours"
    # duration, never as a raw hours-worked number — see the constraint that
    # elapsed time must not be used as a Skill Signal.
    elapsed_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # requirements.md §15 student_reflection: {challenge, ai_usage,
    # changes_after_feedback, remaining_uncertainty[]} — free-form JSON since
    # the exact question set is configurable per the spec, not fixed here.
    student_reflection: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
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
    files = relationship(
        "TaskSubmissionFile", back_populates="submission",
        cascade="all, delete-orphan", order_by="TaskSubmissionFile.uploaded_at",
    )
    enterprise_reviews = relationship(
        "EnterpriseReview", back_populates="submission",
        cascade="all, delete-orphan", order_by="EnterpriseReview.created_at",
    )

class TaskSubmissionFile(Base):
    """Metadata for one uploaded deliverable file (requirements.md §14) — the
    binary itself is stored wherever the caller's upload pipeline puts it
    (e.g. the same GCS bucket domains/task_builder already uses); this row
    only tracks what was uploaded and whether it passed the scan."""
    __tablename__ = "task_submission_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("task_submissions.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    file_url: Mapped[str] = mapped_column(String(1000))
    scan_status: Mapped[FileScanStatus] = mapped_column(SQLEnum(FileScanStatus), default=FileScanStatus.PENDING)
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    submission = relationship("TaskSubmission", back_populates="files")

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

# Business-side decision on 1 submission (requirements.md BUS-12) — deliberately
# separate from TaskReview (mentor decision on the Task itself) and
# mentor_review (mentor decision on a submission, which DOES gate the state
# machine). This is purely informational: BUS-12's constraint is "Không thay
# Evidence" — creating one must never touch TaskSubmission.status or any
# EvidenceClaim, see TaskService.create_enterprise_review.
class EnterpriseReviewDecision(enum.Enum):
    ACCEPTED = "ACCEPTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"

class EnterpriseReview(Base):
    __tablename__ = "enterprise_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("task_submissions.id"))
    reviewed_by: Mapped[int] = mapped_column(Integer)  # business-side actor id, loose ref — no auth (see reviewer_id/mentor_id)
    decision: Mapped[EnterpriseReviewDecision] = mapped_column(SQLEnum(EnterpriseReviewDecision))
    comment: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    submission = relationship("TaskSubmission", back_populates="enterprise_reviews")
