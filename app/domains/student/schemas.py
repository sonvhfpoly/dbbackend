from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from domains.student.constants import (
    EducationLevel,
    RecommendationGenerator,
    RecommendationStatus,
    SkillEventType,
    SourceService,
    StudentStatus,
)


class StudentBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    current_location: str | None = Field(default=None, max_length=100)
    status: StudentStatus = StudentStatus.ACTIVE


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    current_location: str | None = Field(default=None, max_length=100)
    status: StudentStatus | None = None


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    current_location: str | None = None
    status: StudentStatus
    ai_inferred_profile: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StudentProfileBase(BaseModel):
    headline: str | None = None
    school_name: str | None = None
    education_level: EducationLevel | None = None
    major: str | None = None
    graduation_year: int | None = None
    bio: str | None = None
    interests: str | None = None


class StudentProfileUpsert(StudentProfileBase):
    pass


class StudentProfileRead(StudentProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StudentSkillProfileUpsert(BaseModel):
    level: int = Field(default=1, ge=1, le=5)
    confidence: float = Field(default=0.3, ge=0, le=1)
    evidence_count: int = Field(default=0, ge=0)
    summary: str | None = None


class StudentSkillProfileRead(StudentSkillProfileUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    skill_id: int
    last_evidence_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StudentSkillEventCreate(BaseModel):
    skill_id: int
    event_type: SkillEventType = SkillEventType.TASK_EVIDENCE
    source_service: SourceService | None = SourceService.TASK_SERVICE
    source_ref: str | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    level_delta: int = Field(default=0, ge=-5, le=5)
    confidence: float = Field(default=0.5, ge=0, le=1)
    event_metadata: dict | None = None
    occurred_at: datetime | None = None


class StudentSkillEventRead(StudentSkillEventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    created_at: datetime | None = None


class CareerSkillRequirementUpsert(BaseModel):
    skill_id: int
    required_level: int = Field(default=3, ge=1, le=5)
    importance: float = Field(default=1.0, ge=0, le=1)
    rationale: str | None = None


class CareerSkillRequirementRead(CareerSkillRequirementUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    career_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecommendationGenerateRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
    persist: bool = Field(
        default=True,
        description="Upsert this fresh LLM result as the student's current recommendation set.",
    )


class StudentCareerRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    student_id: int
    career_id: int
    career_title: str | None = None
    score: float
    rationale: str | None = None
    strengths: str | None = None
    gaps: str | None = None
    next_steps: str | None = None
    generated_by: RecommendationGenerator = RecommendationGenerator.LLM_V1
    status: RecommendationStatus = RecommendationStatus.DRAFT
    created_at: datetime | None = None
    updated_at: datetime | None = None
