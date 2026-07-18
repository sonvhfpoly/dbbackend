from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from core.config import settings
from .schemas import EducationPathRead, EducationPathCreate, RecommendationRead
from .service import GuidanceService

router = APIRouter(
    prefix="/guidance",
    tags=["AI Guidance"],
)

@router.post("/education-paths/", response_model=EducationPathRead, summary="Register an education/training path")
def create_path(path: EducationPathCreate, db: Session = Depends(get_db)):
    service = GuidanceService(db)
    return service.create_path(path)

@router.get("/education-paths/", response_model=List[EducationPathRead], summary="List all education/training paths")
def list_paths(db: Session = Depends(get_db)):
    service = GuidanceService(db)
    return service.get_all_paths()

@router.post(
    "/students/{student_id}/recommendations",
    response_model=List[RecommendationRead],
    summary="Generate personalized, explainable path recommendations for a student",
    description="Combines the student's ai_inferred_profile (Dev 2) with current Career.market_trend (Dev 1), "
                "asks the LLM to pick from the existing education-path catalog with a mandatory reasoning per "
                "pick, then runs the anti-bias engine (diversity of path type, regional expansion) before persisting.",
)
def generate_recommendations(
    student_id: int,
    count: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    service = GuidanceService(db)
    return service.generate_recommendations(student_id, count)

@router.get(
    "/students/{student_id}/recommendations",
    response_model=List[RecommendationRead],
    summary="List previously generated recommendations for a student",
)
def list_recommendations(student_id: int, db: Session = Depends(get_db)):
    service = GuidanceService(db)
    return service.get_recommendations(student_id)

@router.post(
    "/seed-demo-data",
    tags=["Dev Tools"],
    summary="Populate a sample education-path catalog and demo students (with skill tags) for local testing/demos",
    description="Idempotent for education paths (matched by name) and demo students (matched by email). "
                "Disabled when ENABLE_SEED_ENDPOINT=false, which should be the case in any production deployment.",
)
def seed_demo_data(db: Session = Depends(get_db)):
    if not settings.ENABLE_SEED_ENDPOINT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Data seeding is disabled in this environment")
    service = GuidanceService(db)
    return service.seed_demo_data()
