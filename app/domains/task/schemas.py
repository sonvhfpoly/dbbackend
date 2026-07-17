from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class TaskDifficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"

class TaskInputType(str, Enum):
    DATASET = "DATASET"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"

class SubmissionStatus(str, Enum):
    JOINED = "JOINED"
    SUBMITTED = "SUBMITTED"
    AUTO_CHECK_PASSED = "AUTO_CHECK_PASSED"
    AUTO_CHECK_FAILED = "AUTO_CHECK_FAILED"
    MENTOR_APPROVED = "MENTOR_APPROVED"
    MENTOR_REJECTED = "MENTOR_REJECTED"
    COMPLETED = "COMPLETED"

class CompletionActor(str, Enum):
    AI = "AI"
    MENTOR = "MENTOR"

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

# ---- Task ----

class TaskBase(BaseModel):
    title: str
    # Optional: when omitted, the service asks the chatbot to assess difficulty
    # from the task's title/context/scope instead of requiring the caller to
    # guess it upfront.
    difficulty: Optional[TaskDifficulty] = None
    company_id: int
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

class TaskCreate(TaskBase):
    inputs: List[TaskInputCreate] = Field(default_factory=list)
    outputs: List[TaskOutputCreate] = Field(default_factory=list)
    criteria: List[TaskEvaluationCriterionCreate] = Field(default_factory=list)

class TaskRead(TaskBase):
    id: int
    inputs: List[TaskInputRead] = Field(default_factory=list)
    outputs: List[TaskOutputRead] = Field(default_factory=list)
    criteria: List[TaskEvaluationCriterionRead] = Field(default_factory=list)
    sub_tasks: List["TaskRead"] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

TaskRead.model_rebuild()

# ---- Submission workflow ----

class JoinTaskRequest(BaseModel):
    student_id: int

class SubmitReportRequest(BaseModel):
    # Scoped by (task_id, student_id) rather than submission_id: the student
    # only ever knows the task they joined, not the internal submission row.
    student_id: int
    report_url: str

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
