from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
import enum

# EvidenceClaim state machine (requirements.md section 20):
#   AI_DRAFT -> STUDENT_REVIEWED -> PENDING_MENTOR -> VERIFIED
#   PENDING_MENTOR can also end in NEED_MORE_EVIDENCE or REJECTED instead of VERIFIED.
class EvidenceStatus(enum.Enum):
    AI_DRAFT = "AI_DRAFT"
    STUDENT_REVIEWED = "STUDENT_REVIEWED"
    PENDING_MENTOR = "PENDING_MENTOR"
    VERIFIED = "VERIFIED"
    NEED_MORE_EVIDENCE = "NEED_MORE_EVIDENCE"
    REJECTED = "REJECTED"

class EvidenceSource(enum.Enum):
    FINAL_OUTPUT = "FINAL_OUTPUT"
    STUDENT_REFLECTION = "STUDENT_REFLECTION"
    AI_MENTOR_INTERACTION = "AI_MENTOR_INTERACTION"
    MENTOR_REVIEW = "MENTOR_REVIEW"

class AutonomyLevel(enum.Enum):
    GUIDED = "GUIDED"
    SEMI_INDEPENDENT = "SEMI_INDEPENDENT"
    INDEPENDENT = "INDEPENDENT"

class EvidenceClaim(Base):
    """A claim that a student demonstrated a skill at some level on a task,
    starting as an AI-generated draft and ending either VERIFIED by a mentor
    (which then updates the student's StudentSkillProfile — see
    EvidenceService.mentor_decide) or REJECTED/NEED_MORE_EVIDENCE."""
    __tablename__ = "evidence_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Not a FK: Student lives in a separate domain/table set already reached
    # via plain ids elsewhere in this codebase (see TaskSubmission.student_id).
    student_id: Mapped[int] = mapped_column(Integer, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    claim: Mapped[str] = mapped_column(String(2000))
    observed_actions: Mapped[list] = mapped_column(JSON, default=list)
    evidence_sources: Mapped[list] = mapped_column(JSON, default=list)
    # Snapshots of the task's own T-level/R-level at claim-creation time — not
    # a live FK-following read, so a later change to the task doesn't
    # retroactively rewrite the context evidence was produced under.
    task_complexity: Mapped[str] = mapped_column(String(10))
    risk_level: Mapped[str] = mapped_column(String(10))
    autonomy_level: Mapped[AutonomyLevel] = mapped_column(SQLEnum(AutonomyLevel), default=AutonomyLevel.GUIDED)
    proposed_skill_level: Mapped[str] = mapped_column(String(10))
    status: Mapped[EvidenceStatus] = mapped_column(SQLEnum(EvidenceStatus), default=EvidenceStatus.AI_DRAFT)
    # Not a FK: no Mentor/User identity table yet in this MVP.
    mentor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mentor_comment: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    skill = relationship("Skill")
    task = relationship("Task")
