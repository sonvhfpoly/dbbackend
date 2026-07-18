from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, insert
from .models import Skill, Career, Job, JobSkill, CareerSkill, JobPosting, JobPostingSkill
from typing import Dict, List, Optional, Set, Tuple

class MarketRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- Skill ----

    def get_skill(self, skill_id: int) -> Optional[Skill]:
        return self.db.query(Skill).filter(Skill.id == skill_id).first()

    def list_skills(self, skip: int = 0, limit: int = 100) -> List[Skill]:
        return self.db.query(Skill).order_by(Skill.name.asc()).offset(skip).limit(limit).all()

    def create_skill(self, skill_data: dict) -> Skill:
        db_skill = Skill(**skill_data)
        self.db.add(db_skill)
        self.db.commit()
        self.db.refresh(db_skill)
        return db_skill

    def update_skill(self, skill_id: int, values: dict) -> Optional[Skill]:
        skill = self.get_skill(skill_id)
        if skill is None:
            return None
        for field, value in values.items():
            setattr(skill, field, value)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def delete_skill(self, skill_id: int) -> bool:
        skill = self.get_skill(skill_id)
        if skill is None:
            return False
        self.db.delete(skill)
        self.db.commit()
        return True

    # Matched by name (unique) rather than an external id, since seed/demo data
    # has no stable id to key off of and calling this repeatedly must not raise
    # a duplicate-key error on Skill.name.
    def get_or_create_skill(self, name: str, category: str, description: Optional[str] = None) -> Skill:
        skill = self.db.query(Skill).filter(Skill.name == name).first()
        if skill is None:
            skill = self.create_skill({"name": name, "category": category, "description": description})
        return skill

    # ---- Career (broadest grouping — "nganh", e.g. "Cong nghe thong tin") ----

    def get_career(self, career_id: int) -> Optional[Career]:
        return self.db.query(Career).filter(Career.id == career_id).first()

    def update_career(self, career_id: int, values: dict) -> Optional[Career]:
        career = self.get_career(career_id)
        if career is None:
            return None
        for field, value in values.items():
            setattr(career, field, value)
        self.db.commit()
        self.db.refresh(career)
        return career

    def delete_career(self, career_id: int) -> bool:
        career = self.get_career(career_id)
        if career is None:
            return False
        self.db.delete(career)
        self.db.commit()
        return True

    def get_or_create_career(self, title: str, description: Optional[str] = None) -> Career:
        career = self.db.query(Career).filter(Career.title == title).first()
        if career is None:
            career = Career(title=title, description=description)
            self.db.add(career)
            self.db.commit()
            self.db.refresh(career)
        return career

    def get_careers(self, trend: Optional[str] = None) -> List[Career]:
        query = self.db.query(Career)
        if trend:
            query = query.filter(Career.market_trend == trend)
        return query.all()

    def create_career(self, career_data: dict) -> Career:
        db_career = Career(**career_data)
        self.db.add(db_career)
        self.db.commit()
        self.db.refresh(db_career)
        return db_career

    def add_career_general_skills(self, career_id: int, skill_ids: List[int]) -> None:
        career = self.db.query(Career).filter(Career.id == career_id).first()
        existing_ids = {s.id for s in career.general_skills}
        missing_ids = [sid for sid in skill_ids if sid not in existing_ids]
        if missing_ids:
            career.general_skills.extend(self.db.query(Skill).filter(Skill.id.in_(missing_ids)).all())
        self.db.commit()

    def update_career_trend(self, career_id: int, trend) -> None:
        self.db.query(Career).filter(Career.id == career_id).update({"market_trend": trend})
        self.db.commit()

    # ---- Job (specific job family within a Career, e.g. "DevOps") ----

    # Same idempotency need as get_or_create_skill, plus: if the job already
    # exists we merge in any newly-passed skill_ids instead of overwriting, so
    # re-seeding never drops a link another call already established.
    def get_or_create_job(self, title: str, career_id: int, skill_ids: List[int]) -> Job:
        job = self.db.query(Job).filter(Job.title == title).first()
        if job is None:
            job = Job(title=title, career_id=career_id)
            self.db.add(job)
            self.db.flush()  # assigns job.id so the skills relationship can be populated below

        existing_ids = {s.id for s in job.skills}
        missing_ids = [sid for sid in skill_ids if sid not in existing_ids]
        if missing_ids:
            job.skills.extend(self.db.query(Skill).filter(Skill.id.in_(missing_ids)).all())

        self.db.commit()
        self.db.refresh(job)
        return job

    def get_jobs(self, trend: Optional[str] = None, career_id: Optional[int] = None) -> List[Job]:
        query = self.db.query(Job)
        if trend:
            query = query.filter(Job.market_trend == trend)
        if career_id:
            query = query.filter(Job.career_id == career_id)
        return query.all()

    def create_job(self, job_data: dict) -> Job:
        skill_ids = job_data.pop("skill_ids", [])
        db_job = Job(**job_data)
        if skill_ids:
            db_job.skills = self.db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
        self.db.add(db_job)
        self.db.commit()
        self.db.refresh(db_job)
        return db_job

    def update_job_trend(self, job_id: int, trend) -> None:
        self.db.query(Job).filter(Job.id == job_id).update({"market_trend": trend})
        self.db.commit()

    def get_all_job_ids(self) -> List[int]:
        return [row[0] for row in self.db.query(Job.id).all()]

    def get_job_skill_ids(self, job_id: int) -> List[int]:
        return [
            row[0] for row in
            self.db.query(JobSkill.skill_id).filter(JobSkill.job_id == job_id).all()
        ]

    def get_job_skill_sets(self) -> Dict[int, Set[int]]:
        """job_id -> set of skill_ids, one query — used by the ingest-time
        career/job classification heuristic (no per-row queries)."""
        result: Dict[int, Set[int]] = {}
        for job_id, skill_id in self.db.query(JobSkill.job_id, JobSkill.skill_id).all():
            result.setdefault(job_id, set()).add(skill_id)
        return result

    def get_career_general_skill_sets(self) -> Dict[int, Set[int]]:
        """career_id -> set of skill_ids from CareerSkill — the beginner-
        posting fallback signal when no Job's skill set matches."""
        result: Dict[int, Set[int]] = {}
        for career_id, skill_id in self.db.query(CareerSkill.career_id, CareerSkill.skill_id).all():
            result.setdefault(career_id, set()).add(skill_id)
        return result

    def get_job_career_map(self) -> Dict[int, int]:
        return dict(self.db.query(Job.id, Job.career_id).all())

    # ---- Job posting ingestion ----

    def bulk_create_jobs(self, jobs_data: List[dict]) -> int:
        # skill_ids isn't a JobPosting column — pull it out per row before the
        # bulk insert, but keep the lists (still in row order) to build the
        # JobPostingSkill rows once we know each posting's generated id.
        skill_ids_per_job = [data.pop("skill_ids", []) for data in jobs_data]
        if not jobs_data:
            return 0

        # Two statements total regardless of batch size: a single executemany
        # INSERT...RETURNING (to get the generated ids back, which plain
        # session.add()/flush() per row would also give but one round trip at
        # a time) followed by one bulk insert for the associations.
        result = self.db.execute(insert(JobPosting).returning(JobPosting.id), jobs_data)
        job_posting_ids = [row[0] for row in result]

        job_posting_skill_rows = [
            {"job_posting_id": job_posting_id, "skill_id": skill_id}
            for job_posting_id, skill_ids in zip(job_posting_ids, skill_ids_per_job)
            for skill_id in skill_ids
        ]
        if job_posting_skill_rows:
            self.db.execute(insert(JobPostingSkill), job_posting_skill_rows)

        self.db.commit()
        return len(job_posting_ids)

    # ---- Shared filter helper for the dashboard/aggregate queries below ----

    def _apply_job_filters(self, query, *, location=None, career_id=None,
                            seniority_levels=None, salary_min=None, salary_max=None,
                            start=None, end=None):
        if location:
            query = query.filter(JobPosting.location == location)
        if career_id:
            # Filters directly on JobPosting.career_id (denormalized) — no join
            # to Job needed, since career_id is resolved independently of job_id
            # (see the beginner-posting fallback in models.py/JobPosting).
            query = query.filter(JobPosting.career_id == career_id)
        if seniority_levels:
            # Storage is single-valued per posting; filtering by multiple levels
            # at once (e.g. the UI's combined "Junior/Intern" option) is done
            # here via IN, not by storing multiple levels on one row.
            query = query.filter(JobPosting.seniority_level.in_(seniority_levels))
        if salary_min is not None:
            query = query.filter(JobPosting.salary_max.isnot(None), JobPosting.salary_max >= salary_min)
        if salary_max is not None:
            query = query.filter(JobPosting.salary_min.isnot(None), JobPosting.salary_min <= salary_max)
        if start is not None:
            query = query.filter(JobPosting.posted_at >= start)
        if end is not None:
            query = query.filter(JobPosting.posted_at < end)
        return query

    # ---- Skill demand (existing, location now optional = "Toan quoc") ----

    def get_skill_demand(self, location: Optional[str] = None, since: Optional[datetime] = None) -> List[dict]:
        query = (
            self.db.query(Skill.name, func.count(JobPostingSkill.job_posting_id).label("count"))
            .join(JobPostingSkill)
            .join(JobPosting)
        )
        if location:
            query = query.filter(JobPosting.location == location)
        if since:
            query = query.filter(JobPosting.posted_at >= since)
        results = query.group_by(Skill.name).order_by(func.count(JobPostingSkill.job_posting_id).desc()).all()
        return [{"skill": r[0], "demand": r[1]} for r in results]

    def get_skill_demand_trend(self, location: Optional[str] = None, window_days: int = 30) -> List[dict]:
        """Compares skill demand across two equal-length back-to-back windows,
        optionally scoped to one location ("Toan quoc" = omit location = nationwide)."""
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

    def _skill_counts(self, location: Optional[str], start: datetime, end: datetime):
        query = (
            self.db.query(Skill.name, func.count(JobPostingSkill.job_posting_id))
            .join(JobPostingSkill)
            .join(JobPosting)
            .filter(JobPosting.posted_at >= start, JobPosting.posted_at < end)
        )
        if location:
            query = query.filter(JobPosting.location == location)
        return query.group_by(Skill.name).all()

    def get_job_count_for_skills(self, skill_ids: List[int], start: datetime, end: datetime) -> int:
        """Counts postings that need ANY of skill_ids — a Job's demand signal,
        not a per-skill breakdown. distinct() matters here: a posting tagged with
        two of the job's skills must still only count once."""
        if not skill_ids:
            return 0
        return (
            self.db.query(func.count(func.distinct(JobPostingSkill.job_posting_id)))
            .join(JobPosting, JobPosting.id == JobPostingSkill.job_posting_id)
            .filter(JobPostingSkill.skill_id.in_(skill_ids))
            .filter(JobPosting.posted_at >= start, JobPosting.posted_at < end)
            .scalar()
        ) or 0

    # ---- Dashboard overview aggregates ----

    def count_job_postings(self, *, start=None, end=None, **filters) -> int:
        query = self.db.query(func.count(JobPosting.id))
        query = self._apply_job_filters(query, start=start, end=end, **filters)
        return query.scalar() or 0

    def count_distinct_jobs_with_postings(self, **filters) -> int:
        # COUNT(DISTINCT col) ignores NULLs — postings without a resolved job_id
        # (the beginner fallback case) are correctly excluded from this stat.
        query = self.db.query(func.count(func.distinct(JobPosting.job_id)))
        query = self._apply_job_filters(query, **filters)
        return query.scalar() or 0

    def count_distinct_skills_demanded(self, **filters) -> int:
        query = (
            self.db.query(func.count(func.distinct(JobPostingSkill.skill_id)))
            .join(JobPosting, JobPosting.id == JobPostingSkill.job_posting_id)
        )
        query = self._apply_job_filters(query, **filters)
        return query.scalar() or 0

    def get_last_posting_timestamp(self, **filters) -> Optional[datetime]:
        query = self.db.query(func.max(JobPosting.posted_at))
        query = self._apply_job_filters(query, **filters)
        return query.scalar()

    def get_weekly_posting_counts(self, *, weeks: int = 8, **filters) -> List[Tuple]:
        now = datetime.utcnow()
        start = now - timedelta(weeks=weeks)
        query = self.db.query(
            func.date_trunc("week", JobPosting.posted_at).label("week_start"),
            func.count(JobPosting.id),
        )
        query = self._apply_job_filters(query, start=start, end=now, **filters)
        rows = query.group_by("week_start").order_by("week_start").all()
        return [(row[0].date(), row[1]) for row in rows]

    def get_yearly_average_weekly_count(self, **filters) -> float:
        now = datetime.utcnow()
        start = now - timedelta(days=365)
        total = self.count_job_postings(start=start, end=now, **filters)
        return round(total / (365 / 7), 2)

    def get_location_distribution(self, **filters) -> List[Tuple[str, int]]:
        query = self.db.query(JobPosting.location, func.count(JobPosting.id))
        query = self._apply_job_filters(query, **filters)
        return query.group_by(JobPosting.location).order_by(func.count(JobPosting.id).desc()).all()

    def get_job_demand_within_career(self, career_id: int, window_days: int = 30, **filters) -> List[dict]:
        """Per-Job demand/growth within one Career (the 'drill down to a specific
        job' view) — clones get_skill_demand_trend's two-window shape, grouped
        by Job instead of Skill."""
        now = datetime.utcnow()
        recent_start = now - timedelta(days=window_days)
        previous_start = now - timedelta(days=window_days * 2)

        def counts(start, end):
            query = (
                self.db.query(Job.title, func.count(JobPosting.id))
                .join(JobPosting, JobPosting.job_id == Job.id)
                .filter(Job.career_id == career_id)
            )
            query = self._apply_job_filters(query, start=start, end=end, **filters)
            return dict(query.group_by(Job.title).all())

        recent_counts = counts(recent_start, now)
        previous_counts = counts(previous_start, recent_start)

        titles = set(recent_counts) | set(previous_counts)
        trends = []
        for title in titles:
            recent = recent_counts.get(title, 0)
            previous = previous_counts.get(title, 0)
            growth_rate = ((recent - previous) / previous) if previous > 0 else None
            trends.append({
                "title": title,
                "demand_recent": recent,
                "demand_previous": previous,
                "growth_rate": growth_rate,
            })
        trends.sort(key=lambda t: t["demand_recent"], reverse=True)
        return trends
