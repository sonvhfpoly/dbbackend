from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from datetime import datetime
from domains.student.constants import (
    RecommendationGenerator,
    RecommendationStatus,
    SkillEventType,
    StudentStatus,
)

class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    current_location: Mapped[str] = mapped_column(String(100), nullable=True)
    # JSON, not a fixed set of columns: this is built up incrementally from many
    # different interaction types (game, chat, quiz — see InteractionLog below),
    # so its shape is expected to evolve as the profile-building logic does.
    ai_inferred_profile: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    status: Mapped[str] = mapped_column(
        String(32),
        default=StudentStatus.ACTIVE.value,
        server_default=StudentStatus.ACTIVE.value,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    interactions = relationship("InteractionLog", back_populates="student")

class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    interaction_type: Mapped[str] = mapped_column(String(50)) # e.g., "game", "chat", "quiz"
    payload: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    student = relationship("Student", back_populates="interactions")

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), unique=True, index=True)
    headline: Mapped[str | None] = mapped_column(String(160), nullable=True)
    school_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    major: Mapped[str | None] = mapped_column(String(160), nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    interests: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class StudentSkillProfile(Base):
    __tablename__ = "student_skill_profiles"
    __table_args__ = (UniqueConstraint("student_id", "skill_id", name="uq_student_skill_profile"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.3)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class StudentSkillEvent(Base):
    __tablename__ = "student_skill_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60), default=SkillEventType.TASK_EVIDENCE.value)
    source_service: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level_delta: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CareerSkillRequirement(Base):
    __tablename__ = "career_skill_requirements"
    __table_args__ = (UniqueConstraint("career_id", "skill_id", name="uq_career_skill_requirement"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    required_level: Mapped[int] = mapped_column(Integer, default=3)
    importance: Mapped[float] = mapped_column(Float, default=1.0)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class StudentCareerRecommendation(Base):
    __tablename__ = "student_career_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    gaps: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by: Mapped[str] = mapped_column(
        String(80),
        default=RecommendationGenerator.RULE_BASED_V1.value,
    )
    status: Mapped[str] = mapped_column(String(32), default=RecommendationStatus.DRAFT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
