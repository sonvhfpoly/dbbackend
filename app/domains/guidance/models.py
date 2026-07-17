from sqlalchemy import String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
import enum
from datetime import datetime

class PathType(enum.Enum):
    UNIVERSITY = "UNIVERSITY"
    VOCATIONAL = "VOCATIONAL"
    SHORT_COURSE = "SHORT_COURSE"

class EducationPath(Base):
    __tablename__ = "education_paths"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[PathType] = mapped_column(SQLEnum(PathType))
    duration: Mapped[str] = mapped_column(String(50))
    requirements: Mapped[str] = mapped_column(String(1000), nullable=True)

class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    path_id: Mapped[int] = mapped_column(ForeignKey("education_paths.id"))
    # Required, not optional: every recommendation must be explainable so the
    # student can weigh it as a reference rather than a directive (see the
    # ethical constraints in IMPLEMENTATION_PLAN.md).
    reasoning_explanation: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
