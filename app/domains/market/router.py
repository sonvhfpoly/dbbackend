from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from core.database import get_db
from core.config import settings
from .schemas import (
    SkillRead, SkillCreate, CareerRead, CareerCreate, JobPostingCreate,
    MarketTrend, SkillDemandTrend,
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

@router.get("/careers/", response_model=List[CareerRead], summary="List careers, optionally filtered by market trend")
def list_careers(trend: Optional[MarketTrend] = None, db: Session = Depends(get_db)):
    service = MarketService(db)
    # Typed as the MarketTrend enum (not a raw str) so FastAPI 422s on typos
    # like ?trend=Rising instead of silently matching zero rows.
    return service.get_all_careers(trend.value if trend else None)

@router.post("/careers/", response_model=CareerRead, summary="Register a career and the skills used to track its demand")
def create_career(career: CareerCreate, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.create_career(career)

@router.post("/jobs/bulk", summary="Bulk-ingest job postings and refresh career market trends")
def bulk_ingest_jobs(jobs: List[JobPostingCreate], background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    service = MarketService(db)
    count = service.ingest_jobs(jobs)
    # Recompute Career.market_trend from the freshly ingested data instead of
    # blocking the response on it (plan: 30-day growth rate automation).
    # Reusing the request's `db` session here is safe: FastAPI runs background
    # tasks before the `get_db` dependency's teardown (session.close()) fires.
    background_tasks.add_task(service.update_market_trends)
    return {"message": f"Successfully ingested {count} jobs"}

@router.get("/analytics/skill-demand", summary="Raw skill demand count for a location")
def get_skill_demand(location: str, days: Optional[int] = None, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_demand_analytics(location, days)

@router.get(
    "/analytics/skill-trend",
    response_model=List[SkillDemandTrend],
    summary="Skill demand growth for a location",
    description="Compares job-posting demand per skill across two equal-length back-to-back windows to surface rising/declining and shortage signals per region.",
)
def get_skill_demand_trend(location: str, window_days: int = 30, db: Session = Depends(get_db)):
    service = MarketService(db)
    return service.get_demand_trend(location, window_days)

@router.post(
    "/seed-demo-data",
    tags=["Dev Tools"],
    summary="Populate sample skills, careers, and job postings for local testing/demos",
    description="Idempotent for skills/careers (matched by name); job postings are appended on every call. "
                "Disabled when ENABLE_SEED_ENDPOINT=false, which should be the case in any production deployment.",
)
def seed_demo_data(db: Session = Depends(get_db)):
    if not settings.ENABLE_SEED_ENDPOINT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Data seeding is disabled in this environment")
    service = MarketService(db)
    return service.seed_demo_data()
