from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
# Re-exported (not redefined) — see market/schemas.py for why.
from .models import PathType  # noqa: F401
from domains.task.models import TaskComplexity, EvidenceLevel  # noqa: F401

class EducationPathBase(BaseModel):
    name: str
    type: PathType
    duration: str
    requirements: Optional[str] = None
    location: Optional[str] = Field(default=None, description="Null means available regardless of location (remote/online/nationwide)")

class EducationPathCreate(EducationPathBase):
    pass

class EducationPathRead(EducationPathBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class RecommendationRead(BaseModel):
    id: int
    student_id: int
    path_id: int
    reasoning_explanation: str = Field(description="Why this path was suggested for this student — presented as a reference, not a directive")
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TaskRecommendationRead(BaseModel):
    """Not a persisted row (unlike RecommendationRead above) — generate_recommendations
    computes this fresh on every call, so there's no id/created_at to read back."""
    task_id: int
    title: str
    complexity_level: TaskComplexity
    target_evidence_level: EvidenceLevel
    competency_points: Optional[int] = None
    company_id: int
    reasoning_explanation: str = Field(description="Why this task was suggested toward the target job — presented as a reference, not a directive")
