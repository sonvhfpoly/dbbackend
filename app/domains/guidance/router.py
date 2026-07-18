from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from core.config import settings
from .schemas import EducationPathRead, EducationPathCreate, RecommendationRead, TaskRecommendationRead
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
    response_model=List[TaskRecommendationRead],
    summary="Recommend the student's next open Task toward a target Job",
    description="Compares the student's known skills (StudentSkillProfile, backed by verified evidence) "
                "against the target Job's required skill set (JobSkill) to gauge readiness, then picks open "
                "(mentor-approved, not-yet-started) leaf Tasks at a matching complexity level. Falls back "
                "to an LLM-picked starter set when there's no skill signal to compute a match from (a "
                "brand-new student, or a Job with no configured required skills). Not persisted — call "
                "again any time for a fresh recommendation.",
)
def generate_recommendations(
    student_id: int,
    target_job_id: int = Query(description="The Job the student is aiming for (domains/market Job.id)"),
    count: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    service = GuidanceService(db)
    return service.generate_recommendations(student_id, target_job_id, count)

@router.get(
    "/students/{student_id}/recommendations",
    response_model=List[RecommendationRead],
    summary="List previously generated education-path recommendations for a student",
    description="Historical only: the POST endpoint above now recommends Tasks and doesn't persist, "
                "so this will never return anything created after that change.",
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
