from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
# Re-exported (not redefined) — see market/schemas.py for why.
from .models import EvidenceStatus, EvidenceSource, AutonomyLevel  # noqa: F401

class EvidenceClaimCreate(BaseModel):
    student_id: int
    skill_id: int
    task_id: int
    claim: str = Field(min_length=1, max_length=2000)
    observed_actions: List[str] = Field(default_factory=list)
    evidence_sources: List[EvidenceSource] = Field(default_factory=list)
    task_complexity: str = Field(description="Snapshot of the task's T-level at claim time, e.g. 'T1'")
    risk_level: str = Field(description="Snapshot of the task's R-level at claim time, e.g. 'R0'")
    autonomy_level: AutonomyLevel = AutonomyLevel.GUIDED
    proposed_skill_level: str = Field(description="Skill level this evidence supports, e.g. 'L1'")

class MentorDecisionRequest(BaseModel):
    mentor_id: int
    decision: EvidenceStatus = Field(description="Must be VERIFIED, NEED_MORE_EVIDENCE, or REJECTED")
    comment: Optional[str] = None

class EvidenceClaimRead(BaseModel):
    id: int
    student_id: int
    skill_id: int
    task_id: int
    claim: str
    observed_actions: List[str] = Field(default_factory=list)
    evidence_sources: List[str] = Field(default_factory=list)
    task_complexity: str
    risk_level: str
    autonomy_level: AutonomyLevel
    proposed_skill_level: str
    status: EvidenceStatus
    mentor_id: Optional[int] = None
    mentor_comment: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
