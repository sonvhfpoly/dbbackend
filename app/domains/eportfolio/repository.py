from typing import Optional
from sqlalchemy.orm import Session
from .models import PortfolioShareSetting

class PortfolioRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_share_setting(self, student_id: int) -> Optional[PortfolioShareSetting]:
        return (
            self.db.query(PortfolioShareSetting)
            .filter(PortfolioShareSetting.student_id == student_id)
            .first()
        )

    def upsert_share_setting(self, student_id: int, share_with_business: bool) -> PortfolioShareSetting:
        setting = self.get_share_setting(student_id)
        if setting is None:
            setting = PortfolioShareSetting(student_id=student_id, share_with_business=share_with_business)
            self.db.add(setting)
        else:
            setting.share_with_business = share_with_business
        self.db.commit()
        self.db.refresh(setting)
        return setting
