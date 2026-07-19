from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from core.exceptions import EntityNotFoundException
from .repository import MarketRepository
from .models import MarketTrend, SeniorityLevel
from .schemas import SkillCreate, SkillUpdate, CareerCreate, CareerUpdate, JobCreate, JobPostingCreate
from .seed_data import (
    SEED_SKILLS,
    SEED_CAREER,
    SEED_CAREERS,
    SEED_JOBS,
    SEED_GENERAL_SKILLS,
    SEED_JOB_POSTINGS,
    SEED_SKILL_RENAMES,
)

# A Job/Career's demand is considered meaningfully changed only past this
# threshold, to avoid flip-flopping RISING/DECLINING on small sample noise.
TREND_GROWTH_THRESHOLD = 0.15

# Any shared skill is enough signal, since each Job's/Career's curated skill
# set is small and deliberate, not a noisy bag of keywords.
MIN_JOB_SKILL_OVERLAP = 1
MIN_CAREER_GENERAL_SKILL_OVERLAP = 1

# ASSUMPTION: arbitrary sample-size heuristic for the "confidence" stat card,
# not a statistically rigorous calculation — tune as real data volume is known.
CONFIDENCE_SAMPLE_THRESHOLDS = {"HIGH": 500, "MEDIUM": 100}
# ASSUMPTION: reuses TREND_GROWTH_THRESHOLD (0.15) as the "MODERATE" floor.
GROWTH_SPEED_THRESHOLDS = {"STRONG": 0.30, "MODERATE": TREND_GROWTH_THRESHOLD}

# Cheap keyword heuristic — deliberately NOT a chatbot call, since bulk ingest
# can be hundreds of rows per request and a per-row AI call would be too
# slow/costly for that path (unlike e.g. the task domain's per-task AI calls).
SENIORITY_KEYWORDS = [
    (SeniorityLevel.INTERN, ("intern", "thuc tap")),
    (SeniorityLevel.MANAGER, ("manager", "head of", "director", "truong phong")),
    (SeniorityLevel.SENIOR, ("senior", "sr.", "lead", "site reliability")),
    (SeniorityLevel.JUNIOR, ("junior", "jr.", "fresher")),
]

class MarketService:
    def __init__(self, db: Session):
        self.repo = MarketRepository(db)

    # ---- Skill ----

    def create_skill(self, skill: SkillCreate):
        return self.repo.create_skill(skill.model_dump())

    def get_all_skills(self, skip: int = 0, limit: int = 100):
        return self.repo.list_skills(skip=skip, limit=limit)

    def get_skill(self, skill_id: int):
        skill = self.repo.get_skill(skill_id)
        if skill is None:
            raise EntityNotFoundException("Skill", skill_id)
        return skill

    def update_skill(self, skill_id: int, skill: SkillUpdate):
        updated = self.repo.update_skill(skill_id, skill.model_dump(exclude_unset=True))
        if updated is None:
            raise EntityNotFoundException("Skill", skill_id)
        return updated

    def delete_skill(self, skill_id: int) -> None:
        if not self.repo.delete_skill(skill_id):
            raise EntityNotFoundException("Skill", skill_id)

    # ---- Career (broadest grouping — "nganh") ----

    def get_all_careers(self, trend: str = None):
        return self.repo.get_careers(trend)

    def create_career(self, career: CareerCreate):
        return self.repo.create_career(career.model_dump())

    def get_career(self, career_id: int):
        career = self.repo.get_career(career_id)
        if career is None:
            raise EntityNotFoundException("Career", career_id)
        return career

    def update_career(self, career_id: int, career: CareerUpdate):
        values = career.model_dump(exclude_unset=True)
        if "market_trend" in values and values["market_trend"] is not None:
            values["market_trend"] = MarketTrend(values["market_trend"])
        updated = self.repo.update_career(career_id, values)
        if updated is None:
            raise EntityNotFoundException("Career", career_id)
        return updated

    def delete_career(self, career_id: int) -> None:
        if not self.repo.delete_career(career_id):
            raise EntityNotFoundException("Career", career_id)

    # ---- Job (specific job family within a Career) ----

    def get_all_jobs(self, trend: str = None, career_id: int = None):
        return self.repo.get_jobs(trend, career_id)

    def create_job(self, job: JobCreate):
        return self.repo.create_job(job.model_dump())

    # ---- Job posting ingestion ----

    def ingest_jobs(self, jobs: List[JobPostingCreate]) -> int:
        job_skill_map = self.repo.get_job_skill_sets()
        career_general_skill_map = self.repo.get_career_general_skill_sets()
        job_career_map = self.repo.get_job_career_map()

        jobs_data = [j.model_dump() for j in jobs]
        rows = self._expand_and_resolve(jobs_data, job_skill_map, career_general_skill_map, job_career_map)
        return self.repo.bulk_create_jobs(rows)

    def _expand_and_resolve(
        self,
        jobs_data: List[dict],
        job_skill_map: Dict[int, Set[int]],
        career_general_skill_map: Dict[int, Set[int]],
        job_career_map: Dict[int, int],
    ) -> List[dict]:
        """For each posting: resolve job_id (best skill-overlap match), then
        career_id (from the resolved job, or — the beginner case — a fallback
        match against Career-level general skills when no Job matched at all),
        then fan out into one row per seniority level (never storing multiple
        levels on a single row; see JobPosting.seniority_level)."""
        rows = []
        for raw in jobs_data:
            data = dict(raw)
            levels = data.pop("seniority_levels", None) or self._infer_seniority_levels(data["title"])

            if data.get("job_id") is None:
                data["job_id"] = self._resolve_job_id(data["skill_ids"], job_skill_map)
            if data.get("career_id") is None:
                if data["job_id"] is not None:
                    data["career_id"] = job_career_map.get(data["job_id"])
                else:
                    data["career_id"] = self._resolve_career_id_fallback(data["skill_ids"], career_general_skill_map)
            if data.get("posted_at") is None:
                data["posted_at"] = datetime.utcnow()

            for level in levels:
                rows.append({**data, "seniority_level": level})
        return rows

    @staticmethod
    def _resolve_job_id(skill_ids: List[int], job_skill_map: Dict[int, Set[int]]) -> Optional[int]:
        posting_skills = set(skill_ids)
        best_id, best_overlap = None, 0
        for job_id, job_skills in job_skill_map.items():
            overlap = len(job_skills & posting_skills)
            if overlap > best_overlap:
                best_id, best_overlap = job_id, overlap
        return best_id if best_overlap >= MIN_JOB_SKILL_OVERLAP else None

    @staticmethod
    def _resolve_career_id_fallback(skill_ids: List[int], career_general_skill_map: Dict[int, Set[int]]) -> Optional[int]:
        """Only consulted when _resolve_job_id found no match — e.g. a
        beginner-oriented posting that lists only generic skills (Math,
        Problem Solving, Logical Thinking) rather than a specific job's
        technical skills. Lets the posting still be attributed to the right
        Career/industry even though it can't be pinned to one Job."""
        posting_skills = set(skill_ids)
        best_id, best_overlap = None, 0
        for career_id, general_skills in career_general_skill_map.items():
            overlap = len(general_skills & posting_skills)
            if overlap > best_overlap:
                best_id, best_overlap = career_id, overlap
        return best_id if best_overlap >= MIN_CAREER_GENERAL_SKILL_OVERLAP else None

    @staticmethod
    def _infer_seniority_levels(title: str) -> List[SeniorityLevel]:
        lowered = title.lower()
        matched = [level for level, keywords in SENIORITY_KEYWORDS if any(k in lowered for k in keywords)]
        return matched or [SeniorityLevel.MID]

    # ---- Skill demand analytics (location now optional = "Toan quoc") ----

    def get_demand_analytics(self, location: str = None, days: int = None):
        since = datetime.utcnow() - timedelta(days=days) if days else None
        return self.repo.get_skill_demand(location, since)

    def get_demand_trend(self, location: str = None, window_days: int = 30):
        return self.repo.get_skill_demand_trend(location, window_days)

    # ---- Market trend computation ----

    def update_market_trends(self, window_days: int = 30):
        """Recomputes each Job.market_trend from the growth rate of its linked
        skills' job posting counts across two back-to-back windows, then rolls
        Career.market_trend up from the union of its Jobs' skill sets."""
        now = datetime.utcnow()
        recent_start = now - timedelta(days=window_days)
        previous_start = now - timedelta(days=window_days * 2)

        job_career_map = self.repo.get_job_career_map()
        career_skill_union: Dict[int, Set[int]] = {}

        for job_id in self.repo.get_all_job_ids():
            skill_ids = self.repo.get_job_skill_ids(job_id)
            career_id = job_career_map.get(job_id)
            if career_id is not None:
                career_skill_union.setdefault(career_id, set()).update(skill_ids)

            if not skill_ids:
                continue  # no linked skills means no signal to compute from; leave market_trend as-is rather than guessing

            recent = self.repo.get_job_count_for_skills(skill_ids, recent_start, now)
            previous = self.repo.get_job_count_for_skills(skill_ids, previous_start, recent_start)
            self.repo.update_job_trend(job_id, self._classify_trend(recent, previous))

        for career_id, skill_ids in career_skill_union.items():
            if not skill_ids:
                continue
            recent = self.repo.get_job_count_for_skills(list(skill_ids), recent_start, now)
            previous = self.repo.get_job_count_for_skills(list(skill_ids), previous_start, recent_start)
            self.repo.update_career_trend(career_id, self._classify_trend(recent, previous))

    @staticmethod
    def _classify_trend(recent: int, previous: int) -> MarketTrend:
        if previous == 0:
            # Can't compute a growth rate from a zero baseline (division by
            # zero); treat any current demand as emerging/RISING instead.
            return MarketTrend.RISING if recent > 0 else MarketTrend.STABLE
        growth_rate = (recent - previous) / previous
        if growth_rate >= TREND_GROWTH_THRESHOLD:
            return MarketTrend.RISING
        if growth_rate <= -TREND_GROWTH_THRESHOLD:
            return MarketTrend.DECLINING
        return MarketTrend.STABLE

    # ---- Dashboard overview (stat cards + weekly chart + location distribution) ----

    def get_market_overview(
        self,
        *,
        days: int = 30,
        location: Optional[str] = None,
        career_id: Optional[int] = None,
        seniority_levels: Optional[List[str]] = None,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
    ) -> dict:
        now = datetime.utcnow()
        current_start = now - timedelta(days=days)
        previous_start = now - timedelta(days=days * 2)
        filters = dict(
            location=location, career_id=career_id, seniority_levels=seniority_levels,
            salary_min=salary_min, salary_max=salary_max,
        )

        current_count = self.repo.count_job_postings(start=current_start, end=now, **filters)
        previous_count = self.repo.count_job_postings(start=previous_start, end=current_start, **filters)
        mom_growth = (current_count - previous_count) / previous_count if previous_count > 0 else None

        job_group_count = self.repo.count_distinct_jobs_with_postings(start=current_start, end=now, **filters)
        skill_count = self.repo.count_distinct_skills_demanded(start=current_start, end=now, **filters)

        last_posting_at = self.repo.get_last_posting_timestamp(**filters)
        last_updated_days_ago = (now - last_posting_at).days if last_posting_at else None

        weekly_counts = self.repo.get_weekly_posting_counts(weeks=8, **filters)
        yearly_avg = self.repo.get_yearly_average_weekly_count(**filters)
        location_rows = self.repo.get_location_distribution(**filters)

        return {
            "stats": {
                "total_job_postings": current_count,
                "mom_growth_rate": mom_growth,
                "last_updated_days_ago": last_updated_days_ago,
                "confidence": self._confidence_for_sample(current_count),
                "job_group_count": job_group_count,
                "skill_count": skill_count,
                "growth_speed": self._growth_speed_for_rate(mom_growth),
            },
            "chart": {
                "weekly_counts": [{"week_start": week_start, "count": count} for week_start, count in weekly_counts],
                "yearly_average_weekly_count": yearly_avg,
            },
            "location_distribution": self._to_location_shares(location_rows),
        }

    def get_job_demand(self, career_id: int, window_days: int = 30, **filters) -> List[dict]:
        return self.repo.get_job_demand_within_career(career_id, window_days, **filters)

    @staticmethod
    def _confidence_for_sample(count: int) -> str:
        if count >= CONFIDENCE_SAMPLE_THRESHOLDS["HIGH"]:
            return "HIGH"
        if count >= CONFIDENCE_SAMPLE_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _growth_speed_for_rate(rate: Optional[float]) -> str:
        if rate is None:
            return "STABLE"
        if rate >= GROWTH_SPEED_THRESHOLDS["STRONG"]:
            return "STRONG"
        if rate >= GROWTH_SPEED_THRESHOLDS["MODERATE"]:
            return "MODERATE"
        if rate <= -GROWTH_SPEED_THRESHOLDS["MODERATE"]:
            return "DECLINING"
        return "STABLE"

    @staticmethod
    def _to_location_shares(rows: List[Tuple[str, int]], top_n: int = 3) -> List[dict]:
        total = sum(count for _, count in rows)
        if total == 0:
            return []
        top, rest = rows[:top_n], rows[top_n:]
        shares = [
            {"location": location, "count": count, "percent": round(count / total * 100, 1)}
            for location, count in top
        ]
        rest_count = sum(count for _, count in rest)
        if rest_count > 0:
            shares.append({"location": "Khu vuc khac", "count": rest_count, "percent": round(rest_count / total * 100, 1)})
        return shares

    # ---- Seed ----

    def seed_demo_data(self):
        """Populates a broad Career catalog plus the existing detailed IT demo.

        Careers/Jobs/Skills are idempotent by their unique names. Job postings
        remain append-only so repeated calls can still generate market-history
        volume for dashboard demos.
        """
        for old_name, new_name in SEED_SKILL_RENAMES.items():
            self.repo.rename_skill_if_target_missing(old_name, new_name)

        skill_id_by_name = {
            s["name"]: self.repo.get_or_create_skill(s["name"], s["category"]).id
            for s in SEED_SKILLS
        }

        career_by_title = {
            item["title"]: self.repo.get_or_create_career(
                item["title"],
                description=item.get("description"),
            )
            for item in SEED_CAREERS
        }
        career = career_by_title[SEED_CAREER["title"]]

        for j in SEED_JOBS:
            skill_ids = [skill_id_by_name[name] for name in j["skills"]]
            self.repo.get_or_create_job(j["title"], career.id, skill_ids)

        general_skill_ids = [skill_id_by_name[name] for name in SEED_GENERAL_SKILLS]
        self.repo.add_career_general_skills(career.id, general_skill_ids)

        now = datetime.utcnow()
        jobs_data = [
            {
                "title": j["title"],
                "company": j["company"],
                "location": j["location"],
                "description": j["description"],
                "requirements": j.get("requirements"),
                "benefits": j.get("benefits"),
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "posted_at": now - timedelta(days=j["days_ago"]),
                "skill_ids": [skill_id_by_name[name] for name in j["skills"]],
                "seniority_levels": [SeniorityLevel(s) for s in j["seniority_levels"]] if j.get("seniority_levels") else None,
            }
            for j in SEED_JOB_POSTINGS
        ]

        job_skill_map = self.repo.get_job_skill_sets()
        career_general_skill_map = self.repo.get_career_general_skill_sets()
        job_career_map = self.repo.get_job_career_map()
        rows = self._expand_and_resolve(jobs_data, job_skill_map, career_general_skill_map, job_career_map)
        inserted = self.repo.bulk_create_jobs(rows)
        self.update_market_trends()

        return {
            "skills_seeded": len(SEED_SKILLS),
            "career_id": career.id,
            "careers_seeded": len(SEED_CAREERS),
            "jobs_seeded": len(SEED_JOBS),
            "job_postings_inserted": inserted,
        }
