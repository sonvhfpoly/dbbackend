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

class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(500), nullable=True)

    job_postings = relationship("JobPosting", secondary="job_skills", back_populates="skills")

class Career(Base):
    __tablename__ = "careers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    market_trend: Mapped[MarketTrend] = mapped_column(SQLEnum(MarketTrend), default=MarketTrend.STABLE)

    # Links a career to the skills used to measure its demand/trend from job posting data.
    skills = relationship("Skill", secondary="career_skills")

class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(String(2000))
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    skills = relationship("Skill", secondary="job_skills", back_populates="job_postings")

class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)

class CareerSkill(Base):
    __tablename__ = "career_skills"

    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
