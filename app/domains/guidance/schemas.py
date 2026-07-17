from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from enum import Enum

class PathType(str, Enum):
    UNIVERSITY = "UNIVERSITY"
    VOCATIONAL = "VOCATIONAL"
    SHORT_COURSE = "SHORT_COURSE"

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
