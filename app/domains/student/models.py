from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from datetime import datetime

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

    interactions = relationship("InteractionLog", back_populates="student")

class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    interaction_type: Mapped[str] = mapped_column(String(50)) # e.g., "game", "chat", "quiz"
    payload: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    student = relationship("Student", back_populates="interactions")

class StudentSkillAssociation(Base):
    __tablename__ = "student_skill_association"

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
