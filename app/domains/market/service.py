from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .repository import MarketRepository
from .models import MarketTrend
from .schemas import SkillCreate, CareerCreate, JobPostingCreate
from .seed_data import SEED_SKILLS, SEED_CAREERS, SEED_JOB_POSTINGS
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
        # posted_at is only defaulted here, not at the DB layer, so that a
        # caller backfilling historical postings with a real date isn't
        # silently overwritten — this only fires when the field was omitted.
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
                continue  # no linked skills means no signal to compute from; leave market_trend as-is rather than guessing

            recent = self.repo.get_job_count_for_skills(skill_ids, recent_start, now)
            previous = self.repo.get_job_count_for_skills(skill_ids, previous_start, recent_start)

            if previous == 0:
                # Can't compute a growth rate from a zero baseline (division by
                # zero); treat any current demand as emerging/RISING instead.
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

    def seed_demo_data(self):
        """Populates skills, careers, and a mix of recent/older job postings so the
        demand-trend and market-trend endpoints have something meaningful to show."""
        skill_id_by_name = {
            s["name"]: self.repo.get_or_create_skill(s["name"], s["category"]).id
            for s in SEED_SKILLS
        }

        for c in SEED_CAREERS:
            skill_ids = [skill_id_by_name[name] for name in c["skills"]]
            self.repo.get_or_create_career(c["title"], skill_ids)

        now = datetime.utcnow()
        jobs = [
            {
                "title": j["title"],
                "company": j["company"],
                "location": j["location"],
                "description": j["description"],
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "posted_at": now - timedelta(days=j["days_ago"]),
                "skill_ids": [skill_id_by_name[name] for name in j["skills"]],
            }
            for j in SEED_JOB_POSTINGS
        ]
        inserted = self.repo.bulk_create_jobs(jobs)
        self.update_market_trends()

        return {
            "skills_seeded": len(SEED_SKILLS),
            "careers_seeded": len(SEED_CAREERS),
            "job_postings_inserted": inserted,
        }
