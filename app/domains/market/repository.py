from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, insert
from .models import Skill, Career, JobPosting, JobSkill, CareerSkill
from typing import List, Optional

class MarketRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_skill(self, skill_id: int) -> Optional[Skill]:
        return self.db.query(Skill).filter(Skill.id == skill_id).first()

    def create_skill(self, skill_data: dict) -> Skill:
        db_skill = Skill(**skill_data)
        self.db.add(db_skill)
        self.db.commit()
        self.db.refresh(db_skill)
        return db_skill

    # Matched by name (unique) rather than an external id, since seed/demo data
    # has no stable id to key off of and calling this repeatedly must not raise
    # a duplicate-key error on Skill.name.
    def get_or_create_skill(self, name: str, category: str, description: Optional[str] = None) -> Skill:
        skill = self.db.query(Skill).filter(Skill.name == name).first()
        if skill is None:
            skill = self.create_skill({"name": name, "category": category, "description": description})
        return skill

    # Same idempotency need as get_or_create_skill, plus: if the career already
    # exists we merge in any newly-passed skill_ids instead of overwriting, so
    # re-seeding never drops a link another call already established.
    def get_or_create_career(self, title: str, skill_ids: List[int]) -> Career:
        career = self.db.query(Career).filter(Career.title == title).first()
        if career is None:
            career = Career(title=title)
            self.db.add(career)
            self.db.flush()  # assigns career.id so the skills relationship can be populated below

        existing_ids = {s.id for s in career.skills}
        missing_ids = [sid for sid in skill_ids if sid not in existing_ids]
        if missing_ids:
            career.skills.extend(self.db.query(Skill).filter(Skill.id.in_(missing_ids)).all())

        self.db.commit()
        self.db.refresh(career)
        return career

    def get_careers(self, trend: Optional[str] = None) -> List[Career]:
        query = self.db.query(Career)
        if trend:
            query = query.filter(Career.market_trend == trend)
        return query.all()

    def create_career(self, career_data: dict) -> Career:
        skill_ids = career_data.pop("skill_ids", [])
        db_career = Career(**career_data)
        if skill_ids:
            db_career.skills = self.db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
        self.db.add(db_career)
        self.db.commit()
        self.db.refresh(db_career)
        return db_career

    def bulk_create_jobs(self, jobs_data: List[dict]) -> int:
        # skill_ids isn't a JobPosting column — pull it out per row before the
        # bulk insert, but keep the lists (still in row order) to build the
        # JobSkill rows once we know each posting's generated id.
        skill_ids_per_job = [data.pop("skill_ids", []) for data in jobs_data]
        if not jobs_data:
            return 0

        # Two statements total regardless of batch size: a single executemany
        # INSERT...RETURNING (to get the generated ids back, which plain
        # session.add()/flush() per row would also give but one round trip at
        # a time) followed by one bulk insert for the associations.
        result = self.db.execute(insert(JobPosting).returning(JobPosting.id), jobs_data)
        job_ids = [row[0] for row in result]

        job_skill_rows = [
            {"job_id": job_id, "skill_id": skill_id}
            for job_id, skill_ids in zip(job_ids, skill_ids_per_job)
            for skill_id in skill_ids
        ]
        if job_skill_rows:
            self.db.execute(insert(JobSkill), job_skill_rows)

        self.db.commit()
        return len(job_ids)

    def get_skill_demand(self, location: str, since: Optional[datetime] = None) -> List[dict]:
        query = (
            self.db.query(Skill.name, func.count(JobSkill.job_id).label("count"))
            .join(JobSkill)
            .join(JobPosting)
            .filter(JobPosting.location == location)
        )
        if since:
            query = query.filter(JobPosting.posted_at >= since)
        results = query.group_by(Skill.name).order_by(func.count(JobSkill.job_id).desc()).all()
        return [{"skill": r[0], "demand": r[1]} for r in results]

    def get_skill_demand_trend(self, location: str, window_days: int = 30) -> List[dict]:
        """Compares skill demand for `location` across two equal-length back-to-back windows."""
        now = datetime.utcnow()
        recent_start = now - timedelta(days=window_days)
        previous_start = now - timedelta(days=window_days * 2)

        recent_counts = dict(self._skill_counts(location, recent_start, now))
        previous_counts = dict(self._skill_counts(location, previous_start, recent_start))

        # Union, not intersection: a skill with 0 previous postings but demand
        # now is exactly the "newly emerging" signal we want to surface, and it
        # would silently disappear if we only iterated skills present in both.
        skills = set(recent_counts) | set(previous_counts)
        trends = []
        for name in skills:
            recent = recent_counts.get(name, 0)
            previous = previous_counts.get(name, 0)
            # None (not 0 or inf) when there's no baseline to divide by — the caller
            # decides how to treat "can't compute a rate", we don't fake a number.
            growth_rate = ((recent - previous) / previous) if previous > 0 else None
            trends.append({
                "skill": name,
                "demand_recent": recent,
                "demand_previous": previous,
                "growth_rate": growth_rate,
            })
        trends.sort(key=lambda t: t["demand_recent"], reverse=True)
        return trends

    def _skill_counts(self, location: str, start: datetime, end: datetime):
        return (
            self.db.query(Skill.name, func.count(JobSkill.job_id))
            .join(JobSkill)
            .join(JobPosting)
            .filter(JobPosting.location == location)
            .filter(JobPosting.posted_at >= start, JobPosting.posted_at < end)
            .group_by(Skill.name)
            .all()
        )

    def get_job_count_for_skills(self, skill_ids: List[int], start: datetime, end: datetime) -> int:
        """Counts postings that need ANY of skill_ids — a career's demand signal,
        not a per-skill breakdown. distinct() matters here: a posting tagged with
        two of the career's skills must still only count once."""
        if not skill_ids:
            return 0
        return (
            self.db.query(func.count(func.distinct(JobSkill.job_id)))
            .join(JobPosting, JobPosting.id == JobSkill.job_id)
            .filter(JobSkill.skill_id.in_(skill_ids))
            .filter(JobPosting.posted_at >= start, JobPosting.posted_at < end)
            .scalar()
        ) or 0

    def get_career_skill_ids(self, career_id: int) -> List[int]:
        return [
            row[0] for row in
            self.db.query(CareerSkill.skill_id).filter(CareerSkill.career_id == career_id).all()
        ]

    def get_all_career_ids(self) -> List[int]:
        return [row[0] for row in self.db.query(Career.id).all()]

    def update_career_trend(self, career_id: int, trend) -> None:
        self.db.query(Career).filter(Career.id == career_id).update({"market_trend": trend})
        self.db.commit()
