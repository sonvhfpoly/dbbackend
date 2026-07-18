from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
# Re-exported (not redefined) — see market/schemas.py for why.
from .models import PathType  # noqa: F401

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
