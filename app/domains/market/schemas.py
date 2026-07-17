from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from enum import Enum

class MarketTrend(str, Enum):
    RISING = "RISING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"

class SkillBase(BaseModel):
    name: str
    category: str
    description: Optional[str] = None

class SkillCreate(SkillBase):
    pass

class SkillRead(SkillBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CareerBase(BaseModel):
    title: str
    description: Optional[str] = None
    market_trend: MarketTrend = MarketTrend.STABLE

class CareerCreate(CareerBase):
    skill_ids: List[int] = Field(default_factory=list, description="Skills used to measure this career's demand trend from job posting data")

class CareerRead(CareerBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class JobPostingCreate(BaseModel):
    title: str
    company: str
    location: str
    description: str
    skill_ids: List[int]
    salary_min: Optional[int] = Field(default=None, description="Lower bound of the advertised salary range")
    salary_max: Optional[int] = Field(default=None, description="Upper bound of the advertised salary range")
    posted_at: Optional[datetime] = Field(default=None, description="Actual publish date of the posting, for historical/backfilled data. Defaults to ingestion time if omitted.")

class JobPostingRead(BaseModel):
    id: int
    title: str
    company: str
    location: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posted_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SkillDemandTrend(BaseModel):
    skill: str
    demand_recent: int = Field(description="Job posting count for this skill in the most recent window")
    demand_previous: int = Field(description="Job posting count for this skill in the prior window of equal length")
    growth_rate: Optional[float] = Field(description="(recent - previous) / previous; null when previous window had zero postings")
