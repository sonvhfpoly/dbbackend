import json
from datetime import datetime

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.market.repository import MarketRepository
from domains.chatbot.service import ChatbotService
from domains.task.models import SubmissionStatus, Task, TaskSubmission
from domains.student.constants import RecommendationGenerator, RecommendationStatus
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

CAREER_RECOMMENDATION_SYSTEM_PROMPT = (
    "Bạn là hệ thống gợi ý nghề nghiệp có thể giải thích cho sinh viên. "
    "Dựa CHỈ trên các task sinh viên đã hoàn thành, kỹ năng gắn với các task đó, "
    "kết quả đánh giá và catalog nghề nghiệp được cung cấp, hãy xếp hạng các nghề phù hợp. "
    "Không được tạo career_id hoặc kỹ năng ngoài catalog. Điểm score nằm trong [0,1]. "
    "Lý do phải nêu bằng chứng cụ thể từ task/kỹ năng; không được khẳng định đây là lựa chọn "
    "duy nhất hay chắc chắn. Viết rationale, strengths, gaps và next_steps bằng tiếng Việt. "
    "Trả về duy nhất một JSON object đúng dạng: "
    "{\"recommendations\":[{\"career_id\":1,\"score\":0.8,\"rationale\":\"...\","
    "\"strengths\":\"...\",\"gaps\":\"...\",\"next_steps\":\"...\"}]}."
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
        self.chatbot = ChatbotService()

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

    # ---- Career recommendations (LLM over completed tasks + task skills) ----

    def generate_student_career_recommendations(
        self,
        student_id: int,
        payload: RecommendationGenerateRequest,
    ) -> list[StudentCareerRecommendation]:
        student = self.get_student(student_id)
        completed_tasks = self._completed_task_signals(student_id)
        if not completed_tasks:
            raise BusinessLogicException(
                "Sinh viên chưa hoàn thành task nào nên chưa đủ dữ liệu để gợi ý nghề nghiệp."
            )

        career_catalog = self._career_catalog()
        if not career_catalog:
            raise BusinessLogicException(
                "Catalog chưa có nghề nghiệp để gợi ý.",
                status_code=status.HTTP_409_CONFLICT,
            )

        prompt = json.dumps(
            {
                "student": {
                    "id": student.id,
                    "profile": student.ai_inferred_profile or {},
                },
                "completed_tasks": completed_tasks,
                "career_catalog": career_catalog,
                "limit": payload.limit,
            },
            ensure_ascii=False,
            default=str,
        )
        try:
            raw = self.chatbot.complete(
                [
                    {"role": "system", "content": CAREER_RECOMMENDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                json_mode=True,
            )
            items = self._parse_career_recommendations(raw)
        except Exception as exc:
            raise BusinessLogicException(
                "LLM chưa thể tạo gợi ý nghề nghiệp; vui lòng thử lại.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        careers_by_id = {item["id"]: item for item in career_catalog}
        recommendations: list[StudentCareerRecommendation] = []
        seen_ids: set[int] = set()
        for item in items:
            career_id = item.get("career_id")
            if career_id not in careers_by_id or career_id in seen_ids:
                continue
            seen_ids.add(career_id)
            try:
                score_value = float(item.get("score"))
                rationale = self._required_text(item, "rationale")
            except (TypeError, ValueError):
                continue
            recommendation = StudentCareerRecommendation(
                student_id=student_id,
                career_id=career_id,
                score=round(max(0.0, min(1.0, score_value)), 4),
                rationale=rationale,
                strengths=self._optional_text(item, "strengths"),
                gaps=self._optional_text(item, "gaps"),
                next_steps=self._optional_text(item, "next_steps"),
                generated_by=RecommendationGenerator.LLM_V1.value,
                status=RecommendationStatus.READY_FOR_DEMO.value,
            )
            recommendation.career_title = careers_by_id[career_id]["title"]
            recommendations.append(recommendation)

        recommendations.sort(key=lambda item: item.score, reverse=True)
        recommendations = recommendations[: payload.limit]
        if not recommendations:
            raise BusinessLogicException(
                "LLM không trả về nghề nghiệp hợp lệ trong catalog.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        if payload.persist:
            recommendations = self._replace_career_recommendations(student_id, recommendations)
        return recommendations

    def list_student_career_recommendations(
        self,
        student_id: int,
        limit: int = 20,
    ) -> list[StudentCareerRecommendation]:
        self.get_student(student_id)
        recommendations = (
            self.db.query(StudentCareerRecommendation)
            .filter(StudentCareerRecommendation.student_id == student_id)
            .order_by(StudentCareerRecommendation.score.desc(), StudentCareerRecommendation.updated_at.desc())
            .limit(limit)
            .all()
        )
        careers = {career.id: career.title for career in self.market_repo.get_careers()}
        for recommendation in recommendations:
            recommendation.career_title = careers.get(recommendation.career_id)
        return recommendations

    def _completed_task_signals(self, student_id: int) -> list[dict]:
        rows = (
            self.db.query(TaskSubmission, Task)
            .join(Task, Task.id == TaskSubmission.task_id)
            .filter(
                TaskSubmission.student_id == student_id,
                TaskSubmission.status == SubmissionStatus.COMPLETED,
            )
            .order_by(TaskSubmission.completed_at.asc())
            .all()
        )
        signals = []
        for submission, task in rows:
            scores = [
                {
                    "criterion": score.criterion_id,
                    "score_percent": score.score_percent,
                    "feedback": score.feedback,
                }
                for score in submission.scores
            ]
            signals.append(
                {
                    "task_id": task.id,
                    "title": task.title,
                    "context": task.context,
                    "complexity_level": task.complexity_level.value,
                    "skills": [
                        {"id": skill.id, "name": skill.name, "category": skill.category}
                        for skill in task.skills
                    ],
                    "scores": scores,
                    "mentor_feedback": submission.mentor_feedback,
                    "student_reflection": submission.student_reflection,
                    "completed_at": submission.completed_at,
                }
            )
        return signals

    def _career_catalog(self) -> list[dict]:
        catalog = []
        for career in self.market_repo.get_careers():
            requirements = (
                self.db.query(CareerSkillRequirement)
                .filter(CareerSkillRequirement.career_id == career.id)
                .all()
            )
            skills: dict[int, dict] = {}
            for requirement in requirements:
                skill = self.market_repo.get_skill(requirement.skill_id)
                if skill:
                    skills[skill.id] = {
                        "id": skill.id,
                        "name": skill.name,
                        "required_level": requirement.required_level,
                        "importance": requirement.importance,
                    }
            # Catalogs that have not configured detailed requirements yet can
            # still participate using Career.general_skills and curated Job skills.
            for skill in career.general_skills:
                skills.setdefault(skill.id, {"id": skill.id, "name": skill.name})
            for job in career.jobs:
                for skill in job.skills:
                    skills.setdefault(skill.id, {"id": skill.id, "name": skill.name})
            catalog.append(
                {
                    "id": career.id,
                    "title": career.title,
                    "description": career.description,
                    "market_trend": career.market_trend.value,
                    "skills": list(skills.values()),
                    "jobs": [job.title for job in career.jobs],
                }
            )
        return catalog

    def _replace_career_recommendations(
        self,
        student_id: int,
        generated: list[StudentCareerRecommendation],
    ) -> list[StudentCareerRecommendation]:
        existing = {
            item.career_id: item
            for item in self.db.query(StudentCareerRecommendation)
            .filter(StudentCareerRecommendation.student_id == student_id)
            .all()
        }
        selected_ids = {item.career_id for item in generated}
        for career_id, old in existing.items():
            if career_id not in selected_ids:
                self.db.delete(old)

        persisted = []
        for item in generated:
            row = existing.get(item.career_id)
            if row is None:
                row = item
                self.db.add(row)
            else:
                row.score = item.score
                row.rationale = item.rationale
                row.strengths = item.strengths
                row.gaps = item.gaps
                row.next_steps = item.next_steps
                row.generated_by = item.generated_by
                row.status = item.status
                row.updated_at = datetime.utcnow()
            row.career_title = item.career_title
            persisted.append(row)
        _commit(self.db)
        for row in persisted:
            self.db.refresh(row)
            row.career_title = next(
                item.career_title for item in generated if item.career_id == row.career_id
            )
        return persisted

    @staticmethod
    def _parse_career_recommendations(raw: str) -> list[dict]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        data = json.loads(text)
        items = data.get("recommendations") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError("LLM response must contain a recommendations array")
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _required_text(item: dict, field: str) -> str:
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"LLM response is missing {field}")
        return value.strip()

    @staticmethod
    def _optional_text(item: dict, field: str) -> str | None:
        value = item.get(field)
        return value.strip() if isinstance(value, str) and value.strip() else None

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
