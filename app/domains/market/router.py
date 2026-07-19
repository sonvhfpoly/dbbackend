from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from core.database import get_db
from core.config import settings
from .schemas import (
    SkillRead, SkillCreate, SkillUpdate, CareerRead, CareerCreate, CareerUpdate,
    JobRead, JobCreate, JobPostingCreate,
    MarketTrend, SkillDemandTrend, JobDemandTrend, MarketOverviewRead, SeniorityLevel,
)
from .service import MarketService

router = APIRouter(
    prefix="/market",
    tags=["Market Data"]
)

@router.post("/skills/", response_model=SkillRead, summary="Register a skill")
def create_skill(skill: SkillCreate, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.create_skill(skill)

@router.get("/skills/", response_model=List[SkillRead], summary="List skills")
def list_skills(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_all_skills(skip=skip, limit=limit)

@router.get("/skills/{skill_id}", response_model=SkillRead, summary="Get a skill by id")
def get_skill(skill_id: int, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_skill(skill_id)

@router.patch("/skills/{skill_id}", response_model=SkillRead, summary="Update a skill")
def update_skill(skill_id: int, skill: SkillUpdate, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.update_skill(skill_id, skill)

@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a skill")
def delete_skill(skill_id: int, db: Session = Depends(get_db)):
    service = MarketService(db)
    service.delete_skill(skill_id)

@router.get("/careers/", response_model=List[CareerRead], summary="List careers (industries), optionally filtered by market trend")
def list_careers(trend: Optional[MarketTrend] = None, db: Session = Depends(get_db)):
    service = MarketService(db)
    # Typed as the MarketTrend enum (not a raw str) so FastAPI 422s on typos
    # like ?trend=Rising instead of silently matching zero rows.
    return service.get_all_careers(trend.value if trend else None)

@router.post("/careers/", response_model=CareerRead, summary="Register a career (industry)")
def create_career(career: CareerCreate, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.create_career(career)

@router.get("/careers/{career_id}", response_model=CareerRead, summary="Get a career by id")
def get_career(career_id: int, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_career(career_id)

@router.patch("/careers/{career_id}", response_model=CareerRead, summary="Update a career")
def update_career(career_id: int, career: CareerUpdate, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.update_career(career_id, career)

@router.delete("/careers/{career_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a career")
def delete_career(career_id: int, db: Session = Depends(get_db)):
    service = MarketService(db)
    service.delete_career(career_id)

@router.get("/jobs/", response_model=List[JobRead], summary="List jobs (specific job families), optionally filtered by career or market trend")
def list_jobs(trend: Optional[MarketTrend] = None, career_id: Optional[int] = None, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_all_jobs(trend.value if trend else None, career_id)

@router.post("/jobs/", response_model=JobRead, summary="Register a job (specific job family) under a career")
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.create_job(job)

@router.post("/jobs/bulk", summary="Bulk-ingest job postings and refresh career/job market trends")
def bulk_ingest_jobs(jobs: List[JobPostingCreate], background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    service = MarketService(db)
    count = service.ingest_jobs(jobs)
    # Recompute Job/Career.market_trend from the freshly ingested data instead of
    # blocking the response on it. Reusing the request's `db` session here is
    # safe: FastAPI runs background tasks before the `get_db` dependency's
    # teardown (session.close()) fires.
    background_tasks.add_task(service.update_market_trends)
    return {"message": f"Successfully ingested {count} jobs"}

@router.get("/analytics/skill-demand", summary="Raw skill demand count, optionally scoped to a location")
def get_skill_demand(location: Optional[str] = None, days: Optional[int] = None, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_demand_analytics(location, days)

@router.get(
    "/analytics/skill-trend",
    response_model=List[SkillDemandTrend],
    summary="Skill demand growth, optionally scoped to a location",
    description="Compares job-posting demand per skill across two equal-length back-to-back windows to surface rising/declining and shortage signals. Omit location for a nationwide view.",
)
def get_skill_demand_trend(location: Optional[str] = None, window_days: int = 30, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_demand_trend(location, window_days)

@router.get(
    "/overview",
    response_model=MarketOverviewRead,
    summary="Aggregated skill-trend dashboard data: stat cards, weekly chart, location distribution",
)
def get_market_overview(
    days: int = 30,
    location: Optional[str] = None,
    career_id: Optional[int] = None,
    seniority: Optional[List[SeniorityLevel]] = Query(None),
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = MarketService(db)
    return service.get_market_overview(
        days=days, location=location, career_id=career_id,
        seniority_levels=seniority, salary_min=salary_min, salary_max=salary_max,
    )

@router.get(
    "/careers/{career_id}/jobs",
    response_model=List[JobDemandTrend],
    summary="Per-job demand/growth breakdown within one career (industry)",
    description="Drill-down analogous to /analytics/skill-trend, but grouped by Job instead of Skill, scoped to one career_id.",
)
def get_job_demand(
    career_id: int,
    window_days: int = 30,
    location: Optional[str] = None,
    seniority: Optional[List[SeniorityLevel]] = Query(None),
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = MarketService(db)
    return service.get_job_demand(
        career_id, window_days, location=location,
        seniority_levels=seniority, salary_min=salary_min, salary_max=salary_max,
    )

@router.post(
    "/seed-demo-data",
    tags=["Dev Tools"],
    summary="Populate 100+ careers plus sample jobs, skills, and job postings for local testing/demos",
    description="Idempotent for the career/jobs/skills catalog (matched by name); job postings are appended on every call. "
                "Disabled when ENABLE_SEED_ENDPOINT=false, which should be the case in any production deployment.",
)
def seed_demo_data(db: Session = Depends(get_db)):
    if not settings.ENABLE_SEED_ENDPOINT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Data seeding is disabled in this environment")
    service = MarketService(db)
    return service.seed_demo_data()
