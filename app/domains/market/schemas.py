from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from enum import Enum

class MarketTrend(str, Enum):
    RISING = "RISING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"

class SeniorityLevel(str, Enum):
    INTERN = "INTERN"
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    MANAGER = "MANAGER"

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class GrowthSpeed(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
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

# Career = broadest grouping ("nganh", e.g. "Cong nghe thong tin"). See Job below
# for the specific job-family level.
class CareerBase(BaseModel):
    title: str
    description: Optional[str] = None
    market_trend: MarketTrend = MarketTrend.STABLE

class CareerCreate(CareerBase):
    pass

class CareerRead(CareerBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class JobBase(BaseModel):
    title: str
    description: Optional[str] = None
    career_id: int
    market_trend: MarketTrend = MarketTrend.STABLE

class JobCreate(JobBase):
    skill_ids: List[int] = Field(default_factory=list, description="Skills used to measure this job's demand trend from job posting data")

class JobRead(JobBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class JobPostingCreate(BaseModel):
    title: str
    company: str
    location: str
    description: str
    skill_ids: List[int]
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    salary_min: Optional[int] = Field(default=None, description="Lower bound of the advertised salary range")
    salary_max: Optional[int] = Field(default=None, description="Upper bound of the advertised salary range")
    posted_at: Optional[datetime] = Field(default=None, description="Actual publish date of the posting, for historical/backfilled data. Defaults to ingestion time if omitted.")
    job_id: Optional[int] = Field(default=None, description="Explicit Job to attribute this posting to. Auto-resolved from skill_ids if omitted.")
    career_id: Optional[int] = Field(default=None, description="Explicit Career to attribute this posting to (used when no specific Job can be resolved). Auto-resolved if omitted.")
    seniority_levels: List[SeniorityLevel] = Field(
        default_factory=list,
        description="One or more levels this posting covers. A single value stores directly; if the "
                    "source ad spans multiple levels (e.g. 'Junior/Mid'), the service fans it out into "
                    "one JobPosting row per level rather than storing them together on one row. "
                    "Omit to let the service infer a level from the title.",
    )

class JobPostingRead(BaseModel):
    id: int
    title: str
    company: str
    location: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posted_at: datetime
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    job_id: Optional[int] = None
    career_id: Optional[int] = None
    seniority_level: Optional[SeniorityLevel] = None
    model_config = ConfigDict(from_attributes=True)

class SkillDemandTrend(BaseModel):
    skill: str
    demand_recent: int = Field(description="Job posting count for this skill in the most recent window")
    demand_previous: int = Field(description="Job posting count for this skill in the prior window of equal length")
    growth_rate: Optional[float] = Field(description="(recent - previous) / previous; null when previous window had zero postings")

class JobDemandTrend(BaseModel):
    title: str
    demand_recent: int = Field(description="Job posting count for this Job in the most recent window")
    demand_previous: int = Field(description="Job posting count for this Job in the prior window of equal length")
    growth_rate: Optional[float] = Field(description="(recent - previous) / previous; null when previous window had zero postings")

# ---- Dashboard overview (stat cards + weekly chart + location distribution) ----

class MarketOverviewStats(BaseModel):
    total_job_postings: int
    mom_growth_rate: Optional[float] = Field(description="Month-over-month growth; null when the previous window had zero postings")
    last_updated_days_ago: Optional[int] = Field(description="Derived from MAX(posted_at) in the filtered set — no separate ingestion timestamp exists")
    confidence: ConfidenceLevel
    job_group_count: int = Field(description="Distinct Jobs with at least one matching posting")
    skill_count: int
    growth_speed: GrowthSpeed

class WeeklyPostingCount(BaseModel):
    week_start: date
    count: int

class MarketOverviewChart(BaseModel):
    weekly_counts: List[WeeklyPostingCount]
    yearly_average_weekly_count: float

class LocationShare(BaseModel):
    location: str
    count: int
    percent: float

class MarketOverviewRead(BaseModel):
    stats: MarketOverviewStats
    chart: MarketOverviewChart
    location_distribution: List[LocationShare]
