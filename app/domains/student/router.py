from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from domains.student import service as student_service
from domains.student.schemas import (
    CareerSkillRequirementRead,
    CareerSkillRequirementUpsert,
    RecommendationGenerateRequest,
    StudentCareerRecommendationRead,
    StudentCreate,
    StudentProfileRead,
    StudentProfileUpsert,
    StudentRead,
    StudentSkillEventCreate,
    StudentSkillEventRead,
    StudentSkillProfileRead,
    StudentSkillProfileUpsert,
    StudentUpdate,
)

router = APIRouter(tags=["Student Profile"])


@router.post("/students", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> StudentRead:
    return student_service.StudentProfileService(db).create_student(payload)


@router.get("/students", response_model=list[StudentRead])
def list_students(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)) -> list[StudentRead]:
    return student_service.StudentProfileService(db).list_students(skip=skip, limit=limit)


@router.get("/students/{student_id}", response_model=StudentRead)
def get_student(student_id: int, db: Session = Depends(get_db)) -> StudentRead:
    return student_service.StudentProfileService(db).get_student(student_id)


@router.patch("/students/{student_id}", response_model=StudentRead)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)) -> StudentRead:
    return student_service.StudentProfileService(db).update_student(student_id, payload)


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, db: Session = Depends(get_db)) -> Response:
    student_service.StudentProfileService(db).delete_student(student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/students/{student_id}/profile", response_model=StudentProfileRead)
def upsert_student_profile(
    student_id: int,
    payload: StudentProfileUpsert,
    db: Session = Depends(get_db),
) -> StudentProfileRead:
    return student_service.StudentProfileService(db).upsert_student_profile(student_id, payload)


@router.get("/students/{student_id}/profile", response_model=StudentProfileRead)
def get_student_profile(student_id: int, db: Session = Depends(get_db)) -> StudentProfileRead:
    return student_service.StudentProfileService(db).get_student_profile(student_id)


@router.delete("/students/{student_id}/profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_student_profile(student_id: int, db: Session = Depends(get_db)) -> Response:
    student_service.StudentProfileService(db).delete_student_profile(student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/students/{student_id}/skills/{skill_id}",
    response_model=StudentSkillProfileRead,
)
def upsert_student_skill_profile(
    student_id: int,
    skill_id: int,
    payload: StudentSkillProfileUpsert,
    db: Session = Depends(get_db),
) -> StudentSkillProfileRead:
    return student_service.StudentProfileService(db).upsert_student_skill_profile(student_id, skill_id, payload)


@router.get("/students/{student_id}/skills", response_model=list[StudentSkillProfileRead])
def list_student_skill_profiles(student_id: int, db: Session = Depends(get_db)) -> list[StudentSkillProfileRead]:
    return student_service.StudentProfileService(db).list_student_skill_profiles(student_id)


@router.delete(
    "/students/{student_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_student_skill_profile(student_id: int, skill_id: int, db: Session = Depends(get_db)) -> Response:
    student_service.StudentProfileService(db).delete_student_skill_profile(student_id, skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/students/{student_id}/skill-events",
    response_model=StudentSkillEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_student_skill_event(
    student_id: int,
    payload: StudentSkillEventCreate,
    db: Session = Depends(get_db),
) -> StudentSkillEventRead:
    return student_service.StudentProfileService(db).create_student_skill_event(student_id, payload)


@router.get("/students/{student_id}/skill-events", response_model=list[StudentSkillEventRead])
def list_student_skill_events(
    student_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[StudentSkillEventRead]:
    return student_service.StudentProfileService(db).list_student_skill_events(student_id, skip=skip, limit=limit)


@router.put(
    "/students/careers/{career_id}/skill-requirements",
    response_model=CareerSkillRequirementRead,
)
def upsert_career_skill_requirement(
    career_id: int,
    payload: CareerSkillRequirementUpsert,
    db: Session = Depends(get_db),
) -> CareerSkillRequirementRead:
    return student_service.StudentProfileService(db).upsert_career_skill_requirement(career_id, payload)


@router.get(
    "/students/careers/{career_id}/skill-requirements",
    response_model=list[CareerSkillRequirementRead],
)
def list_career_skill_requirements(career_id: int, db: Session = Depends(get_db)) -> list[CareerSkillRequirementRead]:
    return student_service.StudentProfileService(db).list_career_skill_requirements(career_id)


@router.delete(
    "/students/careers/{career_id}/skill-requirements/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_career_skill_requirement(career_id: int, skill_id: int, db: Session = Depends(get_db)) -> Response:
    student_service.StudentProfileService(db).delete_career_skill_requirement(career_id, skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/students/{student_id}/career-recommendations/generate",
    response_model=list[StudentCareerRecommendationRead],
)
def generate_student_career_recommendations(
    student_id: int,
    payload: RecommendationGenerateRequest,
    db: Session = Depends(get_db),
) -> list[StudentCareerRecommendationRead]:
    return student_service.StudentProfileService(db).generate_student_career_recommendations(student_id, payload)


@router.get(
    "/students/{student_id}/career-recommendations",
    response_model=list[StudentCareerRecommendationRead],
)
def list_student_career_recommendations(
    student_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[StudentCareerRecommendationRead]:
    return student_service.StudentProfileService(db).list_student_career_recommendations(student_id, limit=limit)
