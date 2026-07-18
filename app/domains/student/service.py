from datetime import datetime

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.market.repository import MarketRepository
from domains.student.models import (
    CareerSkillRequirement,
    Student,
    StudentCareerRecommendation,
    StudentProfile,
    StudentSkillEvent,
    StudentSkillProfile,
)
from domains.student.repository import StudentRepository
from domains.student.schemas import (
    CareerSkillRequirementUpsert,
    RecommendationGenerateRequest,
    StudentCreate,
    StudentProfileUpsert,
    StudentSkillEventCreate,
    StudentSkillProfileUpsert,
    StudentUpdate,
)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessLogicException(
            "Resource already exists or violates a unique constraint.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc


class StudentProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.student_repo = StudentRepository(db)
        self.market_repo = MarketRepository(db)

    # ---- Student ----

    def create_student(self, payload: StudentCreate) -> Student:
        student = self.student_repo.create_student(payload.model_dump())
        return student

    def list_students(self, skip: int = 0, limit: int = 50) -> list[Student]:
        return self.student_repo.list_students(skip=skip, limit=limit)

    def get_student(self, student_id: int) -> Student:
        student = self.student_repo.get_student(student_id)
        if student is None:
            raise EntityNotFoundException("Student", student_id)
        return student

    def update_student(self, student_id: int, payload: StudentUpdate) -> Student:
        self.get_student(student_id)
        updated = self.student_repo.update_student(student_id, payload.model_dump(exclude_unset=True))
        _commit(self.db)
        return updated

    def delete_student(self, student_id: int) -> None:
        self.get_student(student_id)
        self.student_repo.delete_student(student_id)

    # ---- Student profile ----

    def upsert_student_profile(self, student_id: int, payload: StudentProfileUpsert) -> StudentProfile:
        self.get_student(student_id)
        profile = self.db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
        if profile is None:
            profile = StudentProfile(student_id=student_id, **payload.model_dump())
            self.db.add(profile)
        else:
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(profile, field, value)
        _commit(self.db)
        self.db.refresh(profile)
        return profile

    def get_student_profile(self, student_id: int) -> StudentProfile:
        self.get_student(student_id)
        profile = self.db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
        if profile is None:
            raise EntityNotFoundException("StudentProfile", student_id)
        return profile

    def delete_student_profile(self, student_id: int) -> None:
        profile = self.get_student_profile(student_id)
        self.db.delete(profile)
        _commit(self.db)

    # ---- Student skill profile ----

    def upsert_student_skill_profile(
        self,
        student_id: int,
        skill_id: int,
        payload: StudentSkillProfileUpsert,
    ) -> StudentSkillProfile:
        self.get_student(student_id)
        self._get_skill(skill_id)
        profile = (
            self.db.query(StudentSkillProfile)
            .filter(
                StudentSkillProfile.student_id == student_id,
                StudentSkillProfile.skill_id == skill_id,
            )
            .first()
        )
        if profile is None:
            profile = StudentSkillProfile(student_id=student_id, skill_id=skill_id, **payload.model_dump())
            self.db.add(profile)
        else:
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(profile, field, value)
        _commit(self.db)
        self.db.refresh(profile)
        return profile

    def list_student_skill_profiles(self, student_id: int) -> list[StudentSkillProfile]:
        self.get_student(student_id)
        return (
            self.db.query(StudentSkillProfile)
            .filter(StudentSkillProfile.student_id == student_id)
            .order_by(StudentSkillProfile.level.desc(), StudentSkillProfile.confidence.desc())
            .all()
        )

    def delete_student_skill_profile(self, student_id: int, skill_id: int) -> None:
        profile = (
            self.db.query(StudentSkillProfile)
            .filter(
                StudentSkillProfile.student_id == student_id,
                StudentSkillProfile.skill_id == skill_id,
            )
            .first()
        )
        if profile is None:
            raise EntityNotFoundException("StudentSkillProfile", f"student_id={student_id}, skill_id={skill_id}")
        self.db.delete(profile)
        _commit(self.db)

    # ---- Student skill events ----

    def create_student_skill_event(
        self,
        student_id: int,
        payload: StudentSkillEventCreate,
    ) -> StudentSkillEvent:
        self.get_student(student_id)
        self._get_skill(payload.skill_id)

        data = payload.model_dump(exclude_none=True)
        event = StudentSkillEvent(student_id=student_id, **data)
        self.db.add(event)

        profile = (
            self.db.query(StudentSkillProfile)
            .filter(
                StudentSkillProfile.student_id == student_id,
                StudentSkillProfile.skill_id == payload.skill_id,
            )
            .first()
        )
        if profile is None:
            profile = StudentSkillProfile(
                student_id=student_id,
                skill_id=payload.skill_id,
                level=max(1, min(5, 1 + payload.level_delta)),
                confidence=payload.confidence,
                evidence_count=1,
                last_evidence_at=payload.occurred_at or datetime.utcnow(),
            )
            self.db.add(profile)
        else:
            profile.level = max(1, min(5, profile.level + payload.level_delta))
            profile.confidence = max(profile.confidence, payload.confidence)
            profile.evidence_count += 1
            profile.last_evidence_at = payload.occurred_at or datetime.utcnow()

        _commit(self.db)
        self.db.refresh(event)
        return event

    def list_student_skill_events(
        self,
        student_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[StudentSkillEvent]:
        self.get_student(student_id)
        return (
            self.db.query(StudentSkillEvent)
            .filter(StudentSkillEvent.student_id == student_id)
            .order_by(StudentSkillEvent.occurred_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ---- Career skill requirements ----

    def upsert_career_skill_requirement(
        self,
        career_id: int,
        payload: CareerSkillRequirementUpsert,
    ) -> CareerSkillRequirement:
        self._get_career(career_id)
        self._get_skill(payload.skill_id)
        requirement = (
            self.db.query(CareerSkillRequirement)
            .filter(
                CareerSkillRequirement.career_id == career_id,
                CareerSkillRequirement.skill_id == payload.skill_id,
            )
            .first()
        )
        if requirement is None:
            requirement = CareerSkillRequirement(career_id=career_id, **payload.model_dump())
            self.db.add(requirement)
        else:
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(requirement, field, value)
        _commit(self.db)
        self.db.refresh(requirement)
        return requirement

    def list_career_skill_requirements(self, career_id: int) -> list[CareerSkillRequirement]:
        self._get_career(career_id)
        return (
            self.db.query(CareerSkillRequirement)
            .filter(CareerSkillRequirement.career_id == career_id)
            .order_by(CareerSkillRequirement.importance.desc())
            .all()
        )

    def delete_career_skill_requirement(self, career_id: int, skill_id: int) -> None:
        requirement = (
            self.db.query(CareerSkillRequirement)
            .filter(
                CareerSkillRequirement.career_id == career_id,
                CareerSkillRequirement.skill_id == skill_id,
            )
            .first()
        )
        if requirement is None:
            raise EntityNotFoundException("CareerSkillRequirement", f"career_id={career_id}, skill_id={skill_id}")
        self.db.delete(requirement)
        _commit(self.db)

    # ---- Career recommendations (rule-based skill-gap scoring) ----

    def generate_student_career_recommendations(
        self,
        student_id: int,
        payload: RecommendationGenerateRequest,
    ) -> list[StudentCareerRecommendation]:
        self.get_student(student_id)
        skill_profiles = {
            profile.skill_id: profile
            for profile in self.db.query(StudentSkillProfile)
            .filter(StudentSkillProfile.student_id == student_id)
            .all()
        }
        careers = self.market_repo.get_careers()
        recommendations: list[StudentCareerRecommendation] = []

        for career in careers:
            requirements = (
                self.db.query(CareerSkillRequirement)
                .filter(CareerSkillRequirement.career_id == career.id)
                .all()
            )
            if not requirements:
                continue

            total_weight = sum(requirement.importance for requirement in requirements) or 1
            matched_weight = 0.0
            strengths: list[str] = []
            gaps: list[str] = []

            for requirement in requirements:
                profile = skill_profiles.get(requirement.skill_id)
                current_level = profile.level if profile else 0
                fit_ratio = min(current_level / requirement.required_level, 1.0)
                matched_weight += fit_ratio * requirement.importance
                skill = self.market_repo.get_skill(requirement.skill_id)
                if current_level >= requirement.required_level:
                    strengths.append(f"{skill.name}: level {current_level}/{requirement.required_level}")
                else:
                    gaps.append(f"{skill.name}: can level {requirement.required_level}, hien co {current_level}")

            score = round(matched_weight / total_weight, 4)
            recommendation = StudentCareerRecommendation(
                student_id=student_id,
                career_id=career.id,
                score=score,
                rationale=f"Phu hop {round(score * 100)}% voi yeu cau ky nang cua nghe {career.title}.",
                strengths="; ".join(strengths) if strengths else None,
                gaps="; ".join(gaps) if gaps else None,
                next_steps="Tap trung bo sung cac skill con thieu va lam task co bang chung ro rang.",
            )
            recommendations.append(recommendation)

        recommendations.sort(key=lambda item: item.score, reverse=True)
        recommendations = recommendations[: payload.limit]

        if payload.persist:
            for recommendation in recommendations:
                self.db.add(recommendation)
            _commit(self.db)
            for recommendation in recommendations:
                self.db.refresh(recommendation)

        return recommendations

    def list_student_career_recommendations(
        self,
        student_id: int,
        limit: int = 20,
    ) -> list[StudentCareerRecommendation]:
        self.get_student(student_id)
        return (
            self.db.query(StudentCareerRecommendation)
            .filter(StudentCareerRecommendation.student_id == student_id)
            .order_by(StudentCareerRecommendation.created_at.desc(), StudentCareerRecommendation.score.desc())
            .limit(limit)
            .all()
        )

    def _get_skill(self, skill_id: int):
        skill = self.market_repo.get_skill(skill_id)
        if skill is None:
            raise EntityNotFoundException("Skill", skill_id)
        return skill

    def _get_career(self, career_id: int):
        career = self.market_repo.get_career(career_id)
        if career is None:
            raise EntityNotFoundException("Career", career_id)
        return career
