from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .repository import MarketRepository
from .models import MarketTrend
from .schemas import SkillCreate, CareerCreate, JobPostingCreate
from typing import List

# A career's demand is considered meaningfully changed only past this threshold,
# to avoid flip-flopping RISING/DECLINING on small sample noise.
TREND_GROWTH_THRESHOLD = 0.15

class MarketService:
    def __init__(self, db: Session):
        self.repo = MarketRepository(db)

    def create_skill(self, skill: SkillCreate):
        return self.repo.create_skill(skill.model_dump())

    def get_all_careers(self, trend: str = None):
        return self.repo.get_careers(trend)

    def create_career(self, career: CareerCreate):
        return self.repo.create_career(career.model_dump())

    def ingest_jobs(self, jobs: List[JobPostingCreate]):
        data = []
        for j in jobs:
            job_dict = j.model_dump()
            if job_dict.get("posted_at") is None:
                job_dict["posted_at"] = datetime.utcnow()
            data.append(job_dict)
        return self.repo.bulk_create_jobs(data)

    def get_demand_analytics(self, location: str, days: int = None):
        since = datetime.utcnow() - timedelta(days=days) if days else None
        return self.repo.get_skill_demand(location, since)

    def get_demand_trend(self, location: str, window_days: int = 30):
        return self.repo.get_skill_demand_trend(location, window_days)

    def update_market_trends(self, window_days: int = 30):
        """Recomputes each Career.market_trend from the growth rate of its linked
        skills' job posting counts across two back-to-back windows."""
        now = datetime.utcnow()
        recent_start = now - timedelta(days=window_days)
        previous_start = now - timedelta(days=window_days * 2)

        for career_id in self.repo.get_all_career_ids():
            skill_ids = self.repo.get_career_skill_ids(career_id)
            if not skill_ids:
                continue

            recent = self.repo.get_job_count_for_skills(skill_ids, recent_start, now)
            previous = self.repo.get_job_count_for_skills(skill_ids, previous_start, recent_start)

            if previous == 0:
                trend = MarketTrend.RISING if recent > 0 else MarketTrend.STABLE
            else:
                growth_rate = (recent - previous) / previous
                if growth_rate >= TREND_GROWTH_THRESHOLD:
                    trend = MarketTrend.RISING
                elif growth_rate <= -TREND_GROWTH_THRESHOLD:
                    trend = MarketTrend.DECLINING
                else:
                    trend = MarketTrend.STABLE

            self.repo.update_career_trend(career_id, trend)
