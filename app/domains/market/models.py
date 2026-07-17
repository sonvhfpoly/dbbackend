from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
import enum

class MarketTrend(enum.Enum):
    RISING = "RISING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"

# Assumption: UI only shows one combined "Junior / Intern" filter option, so the
# full level taxonomy isn't visible — a standard 5-tier ladder is used here.
class SeniorityLevel(enum.Enum):
    INTERN = "INTERN"
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    MANAGER = "MANAGER"

class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(500), nullable=True)

    job_postings = relationship("JobPosting", secondary="job_posting_skills", back_populates="skills")

# Career = the broadest grouping ("nganh", e.g. "Cong nghe thong tin"). Job (below)
# is the specific job family within it (e.g. "DevOps", "Backend Developer").
class Career(Base):
    __tablename__ = "careers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    # Rolled up from the market_trend of this career's Jobs (union of their
    # skill sets) rather than computed directly here — see
    # MarketService.update_market_trends.
    market_trend: Mapped[MarketTrend] = mapped_column(SQLEnum(MarketTrend), default=MarketTrend.STABLE)

    jobs = relationship("Job", back_populates="career")
    general_skills = relationship("Skill", secondary="career_skills")

# Job = a specific job family/role within a Career (e.g. "DevOps", "MLOps",
# "Backend Developer"). Deliberately named close to JobPosting/JobPostingSkill:
# Job is the curated catalog entry (like Career/Skill), JobPosting is one
# ingested listing instance.
class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id"), index=True)
    market_trend: Mapped[MarketTrend] = mapped_column(SQLEnum(MarketTrend), default=MarketTrend.STABLE)

    career = relationship("Career", back_populates="jobs")
    # Curated once (defines what this job family looks like), distinct from
    # JobPostingSkill below (comes from ingestion, tags one specific posting).
    skills = relationship("Skill", secondary="job_skills")

class JobSkill(Base):
    """Curated skill set that defines one Job (used to compute its market_trend).
    Distinct from JobPostingSkill, which tags what one ingested JobPosting actually asked for."""
    __tablename__ = "job_skills"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)

class CareerSkill(Base):
    """Foundational/general skills for a whole Career (e.g. Math, Problem Solving,
    Logical Thinking) — NOT used to compute market_trend (that's JobSkill's job).
    Used only as a fallback classification signal: a beginner-oriented posting
    that lists only generic skills (no job-specific ones) can still be
    attributed to the right Career even though it can't be pinned to one Job."""
    __tablename__ = "career_skills"

    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)

class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(String(2000))
    requirements: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    benefits: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    # Nullable because not every source posting discloses pay; a range (not a
    # single figure) since that's how most job ads actually advertise salary.
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Indexed because every trend/demand query filters on this range.
    posted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Single-valued: one posting is for exactly one Job. When a source ad
    # spans multiple levels (e.g. "Junior/Mid"), it's fanned out into multiple
    # JobPosting rows at ingest time instead of storing multiple levels here
    # (see MarketService.ingest_jobs) — keeps this column simple and queryable.
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    # Denormalized and resolved independently of job_id: when a Job match is
    # found, career_id = job.career_id; when it isn't (a beginner posting with
    # only generic skills, matched only via CareerSkill), career_id can still
    # be set while job_id stays null. This lets industry-level filtering work
    # even for postings that can't be pinned to a specific Job.
    career_id: Mapped[Optional[int]] = mapped_column(ForeignKey("careers.id"), nullable=True, index=True)
    # Single-valued (see job_id comment above for the multi-level handling rationale).
    seniority_level: Mapped[Optional[SeniorityLevel]] = mapped_column(SQLEnum(SeniorityLevel), nullable=True, index=True)

    job = relationship("Job")
    career = relationship("Career")
    skills = relationship("Skill", secondary="job_posting_skills", back_populates="job_postings")

class JobPostingSkill(Base):
    """Which skills a given job posting asks for — comes from ingestion, one row
    per (posting, skill). Distinct from JobSkill, which is Job's curated catalog skillset."""
    __tablename__ = "job_posting_skills"

    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
