from pydantic import BaseModel, ConfigDict
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

class EducationPathCreate(EducationPathBase):
    pass

class EducationPathRead(EducationPathBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class RecommendationRead(BaseModel):
    id: int
    student_id: int
    path_id: int
    reasoning_explanation: str
    created_at: str
    model_config = ConfigDict(from_attributes=True)
