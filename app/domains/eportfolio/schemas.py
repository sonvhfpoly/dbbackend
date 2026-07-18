from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ShareSettingUpdate(BaseModel):
    share_with_business: bool

class ShareSettingRead(BaseModel):
    student_id: int
    share_with_business: bool
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PortfolioSkill(BaseModel):
    skill_id: int
    skill_name: str
    level: int
    confidence: float
    evidence_count: int

class PortfolioEvidence(BaseModel):
    evidence_id: int
    skill_id: int
    task_id: int
    claim: str
    proposed_skill_level: str
    mentor_comment: Optional[str] = None
    decided_at: Optional[datetime] = None

class PortfolioTask(BaseModel):
    task_id: int
    title: str
    completed_at: Optional[datetime] = None
    points_awarded: Optional[int] = None

class PortfolioCareerSuggestion(BaseModel):
    career_id: int
    career_title: str
    score: float
    rationale: Optional[str] = None

class PortfolioNextTask(BaseModel):
    task_id: int
    title: str
    target_evidence_level: str

# ---- Student view: full detail, student owns this ----

class EPortfolioRead(BaseModel):
    student_id: int
    full_name: str
    headline: Optional[str] = None
    verified_skills: List[PortfolioSkill] = Field(default_factory=list)
    verified_evidence: List[PortfolioEvidence] = Field(default_factory=list)
    completed_tasks: List[PortfolioTask] = Field(default_factory=list)
    career_suggestions: List[PortfolioCareerSuggestion] = Field(default_factory=list)
    suggested_next_tasks: List[PortfolioNextTask] = Field(default_factory=list)
    share_with_business: bool = False

# ---- Business view: same shape, but the service filters what's populated
# (no raw AI chat / private reflection / activity log — those were never
# collected here anyway, see requirements.md section 21) and career
# suggestions are omitted unless the student opted to share interests. ----

class EPortfolioBusinessView(BaseModel):
    student_id: int
    full_name: str
    headline: Optional[str] = None
    verified_skills: List[PortfolioSkill] = Field(default_factory=list)
    selected_evidence: List[PortfolioEvidence] = Field(default_factory=list)
    selected_tasks: List[PortfolioTask] = Field(default_factory=list)
