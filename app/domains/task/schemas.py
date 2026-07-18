from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field
# Re-exported (not redefined) — see market/schemas.py for why. TaskDifficulty
# was retired: complexity_level (T1-T3) is now the single source of truth
# for "how hard is this task", replacing the old parallel EASY/MEDIUM/HARD scale.
from .models import (  # noqa: F401
    TaskInputType, SubmissionStatus, CompletionActor,
    TaskComplexity, TaskRiskLevel, EvidenceLevel, TaskReviewStatus, FileScanStatus,
)

class StudentReflection(BaseModel):
    """requirements.md §15 — the exact question set is 'Configurable' (STU-12),
    so every field here is optional rather than a fixed required form."""
    challenge: Optional[str] = None
    ai_usage: Optional[str] = None
    changes_after_feedback: Optional[str] = None
    remaining_uncertainty: List[str] = Field(default_factory=list)

# ---- Company ----

class CompanyBase(BaseModel):
    name: str
    slug: str = Field(description="URL-friendly identifier, e.g. 'tiki-corporation'")
    logo_url: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    website_url: Optional[str] = None
    contact_email: Optional[str] = None
    is_verified: bool = False

class CompanyCreate(CompanyBase):
    pass

class CompanyRead(CompanyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# ---- Task children ----

class TaskInputCreate(BaseModel):
    name: str
    description: str
    input_type: TaskInputType = TaskInputType.OTHER
    is_restricted: bool = False

class TaskInputRead(TaskInputCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class TaskOutputCreate(BaseModel):
    sort_order: int = 0
    description: str

class TaskOutputRead(TaskOutputCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class TaskEvaluationCriterionCreate(BaseModel):
    criterion: str
    weight_percent: int = Field(ge=0, le=100)

class TaskEvaluationCriterionRead(TaskEvaluationCriterionCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class TaskSkillRead(BaseModel):
    id: int
    name: str
    category: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class SetTaskSkillsRequest(BaseModel):
    skill_ids: List[int] = Field(default_factory=list)

# ---- Task ----

class TaskBase(BaseModel):
    title: str
    company_id: Optional[int] = Field(default=None, description="Omit (or pass an id that isn't registered) to fall back to a shared placeholder company — task creation never fails for a missing/invalid company.")
    parent_task_id: Optional[int] = Field(default=None, description="Set to make this a sub-task. The referenced task must itself be a root task (max depth 2).")
    sort_order: int = 0
    estimated_hours_min: int
    estimated_hours_max: int
    competency_points: Optional[int] = Field(default=None, description="Required for a leaf task; must be left null when the task has sub-tasks (points are summed from them instead).")
    context: str
    scope_included: List[str] = Field(default_factory=list)
    scope_excluded: List[str] = Field(default_factory=list)
    requires_auto_check: bool = False
    requires_mentor_approval: bool = True
    mentor_approval_sla_hours: Optional[int] = None
    data_privacy_notice: Optional[str] = None
    deadline: Optional[datetime] = Field(default=None, description="Business's desired completion date (requirements.md §7.1) — optional, display/planning only.")
    checkpoints: List[str] = Field(default_factory=list, description="Milestones the student is expected to hit while working outside WORKLAB — display-only.")
    # Optional: when omitted, the service asks the chatbot to assess T-level
    # from the task's title/context/scope instead of requiring the caller to
    # guess it upfront (same behavior the old, now-retired difficulty field had).
    complexity_level: Optional[TaskComplexity] = Field(default=None, description="T-level, as proposed by the business/AI. A mentor review may override this.")
    risk_level: TaskRiskLevel = Field(default=TaskRiskLevel.R0, description="R-level, as proposed by the business/AI. R2/R3 can never reach APPROVED review status.")
    target_evidence_level: EvidenceLevel = Field(default=EvidenceLevel.L1, description="Skill level this task is meant to produce evidence for.")

class TaskCreate(TaskBase):
    inputs: List[TaskInputCreate] = Field(default_factory=list)
    outputs: List[TaskOutputCreate] = Field(default_factory=list)
    criteria: List[TaskEvaluationCriterionCreate] = Field(default_factory=list)
    skill_ids: List[int] = Field(
        default_factory=list,
        description="Existing market Skill ids exercised by this task.",
    )
    skip_ai_planning: bool = Field(
        default=False,
        description="Skip the LLM call for T-level assessment and sub-task auto-splitting entirely — "
                    "the task is created as a single flat task using complexity_level (or its T1 default) "
                    "as-is. Useful for demos/tests that don't want an LLM round-trip or unpredictable splitting.",
    )

class TaskRead(TaskBase):
    id: int
    review_status: TaskReviewStatus = TaskReviewStatus.PENDING_MENTOR_APPROVAL
    inputs: List[TaskInputRead] = Field(default_factory=list)
    outputs: List[TaskOutputRead] = Field(default_factory=list)
    criteria: List[TaskEvaluationCriterionRead] = Field(default_factory=list)
    skills: List[TaskSkillRead] = Field(default_factory=list)
    sub_tasks: List["TaskRead"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

TaskRead.model_rebuild()

# ---- Task review (mentor approves/rejects the Task itself) ----

class TaskReviewRequest(BaseModel):
    reviewer_id: int = Field(description="Mentor id making the decision (no auth/identity system yet — passed explicitly)")
    decision: TaskReviewStatus = Field(description="Must be APPROVED, REJECTED, or NEED_MORE_INFO — never PENDING_MENTOR_APPROVAL")
    approved_complexity: Optional[TaskComplexity] = Field(default=None, description="Overrides the task's complexity_level when the mentor disagrees with the proposed T-level")
    approved_risk: Optional[TaskRiskLevel] = Field(default=None, description="Overrides the task's risk_level. APPROVED is rejected by the server if this (or the task's existing risk_level) is R2/R3.")
    approved_evidence_level: Optional[EvidenceLevel] = Field(default=None, description="Overrides the task's target_evidence_level")
    comment: Optional[str] = None

class TaskReviewRead(BaseModel):
    id: int
    task_id: int
    reviewer_id: int
    decision: TaskReviewStatus
    approved_complexity: Optional[TaskComplexity] = None
    approved_risk: Optional[TaskRiskLevel] = None
    approved_evidence_level: Optional[EvidenceLevel] = None
    comment: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ---- Submission workflow ----

class JoinTaskRequest(BaseModel):
    student_id: int

class SubmitReportRequest(BaseModel):
    # Scoped by (task_id, student_id) rather than submission_id: the student
    # only ever knows the task they joined, not the internal submission row.
    student_id: int
    report_url: str
    student_reflection: Optional[StudentReflection] = None

class RegisterSubmissionFileRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str
    size_bytes: int = Field(gt=0, le=50 * 1024 * 1024, description="MVP default cap: 50 MB/file (requirements.md §14)")
    file_url: str

class TaskSubmissionFileRead(BaseModel):
    id: int
    submission_id: int
    file_name: str
    mime_type: str
    size_bytes: int
    file_url: str
    scan_status: FileScanStatus
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MentorReviewRequest(BaseModel):
    approved: bool
    feedback: Optional[str] = None

class CompleteSubmissionRequest(BaseModel):
    completed_by: CompletionActor

class ScoreCriterionRequest(BaseModel):
    criterion_id: int
    score_percent: int = Field(ge=0, le=100)
    feedback: Optional[str] = None
    scored_by: CompletionActor

class TaskSubmissionRead(BaseModel):
    id: int
    task_id: int
    student_id: int
    status: SubmissionStatus
    joined_at: datetime
    report_url: Optional[str] = None
    submitted_at: Optional[datetime] = None
    elapsed_seconds: Optional[int] = Field(default=None, description="joined_at -> submitted_at, in seconds. Display-only (e.g. 'N days M hours') — must never be used as a Skill Signal.")
    student_reflection: Optional[StudentReflection] = None
    auto_check_result: Optional[Any] = None
    mentor_feedback: Optional[str] = None
    mentor_decision_at: Optional[datetime] = None
    completed_by: Optional[CompletionActor] = None
    points_awarded: Optional[int] = None
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class TaskSubmissionScoreRead(BaseModel):
    id: int
    submission_id: int
    criterion_id: int
    score_percent: int
    feedback: Optional[str] = None
    scored_by: CompletionActor
    scored_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SubTaskProgress(BaseModel):
    task_id: int
    title: str
    status: Optional[SubmissionStatus] = Field(default=None, description="Null if the student hasn't joined this sub-task yet")
    points_awarded: Optional[int] = None

class TaskProgressRead(BaseModel):
    task_id: int
    student_id: int
    is_fully_completed: bool
    total_points_awarded: Optional[int] = None
    # Populated only when the task has sub-tasks.
    sub_tasks: List[SubTaskProgress] = Field(default_factory=list)
    # Populated only when the task is a leaf (no sub-tasks).
    submission: Optional[TaskSubmissionRead] = None
