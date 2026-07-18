from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base

class PortfolioShareSetting(Base):
    """A student's consent to let a business view their (filtered) ePortfolio —
    requirements.md section 21: 'Bắt buộc consent'. One row per student;
    absence of a row (or share_with_business=False) means no business can
    see anything beyond what's already visible to them directly on a task."""
    __tablename__ = "portfolio_share_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), unique=True, index=True)
    share_with_business: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
