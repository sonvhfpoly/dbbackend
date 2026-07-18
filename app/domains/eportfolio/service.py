from sqlalchemy.orm import Session
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.student.service import StudentProfileService
from domains.evidence.repository import EvidenceRepository
from domains.evidence.models import EvidenceStatus
from domains.task.repository import TaskRepository
from domains.task.models import SubmissionStatus, TaskReviewStatus
from domains.market.repository import MarketRepository
from .repository import PortfolioRepository
from .schemas import (
    EPortfolioRead, EPortfolioBusinessView, PortfolioSkill, PortfolioEvidence,
    PortfolioTask, PortfolioCareerSuggestion, PortfolioNextTask,
)

class EPortfolioService:
    def __init__(self, db: Session):
        self.db = db
        self.student_service = StudentProfileService(db)
        self.evidence_repo = EvidenceRepository(db)
        self.task_repo = TaskRepository(db)
        self.market_repo = MarketRepository(db)
        self.portfolio_repo = PortfolioRepository(db)

    def _verified_skills(self, student_id: int) -> list[PortfolioSkill]:
        profiles = self.student_service.list_student_skill_profiles(student_id)
        skills = []
        for profile in profiles:
            skill = self.market_repo.get_skill(profile.skill_id)
            skills.append(PortfolioSkill(
                skill_id=profile.skill_id,
                skill_name=skill.name if skill else f"skill_{profile.skill_id}",
                level=profile.level,
                confidence=profile.confidence,
                evidence_count=profile.evidence_count,
            ))
        return skills

    def _verified_evidence(self, student_id: int) -> list[PortfolioEvidence]:
        claims = self.evidence_repo.list_by_student(student_id, status=EvidenceStatus.VERIFIED.value)
        return [
            PortfolioEvidence(
                evidence_id=c.id,
                skill_id=c.skill_id,
                task_id=c.task_id,
                claim=c.claim,
                proposed_skill_level=c.proposed_skill_level,
                mentor_comment=c.mentor_comment,
                decided_at=c.decided_at,
            )
            for c in claims
        ]

    def _completed_tasks(self, student_id: int) -> list[PortfolioTask]:
        submissions = self.task_repo.list_submissions(student_id=student_id)
        tasks = []
        for submission in submissions:
            if submission.status != SubmissionStatus.COMPLETED:
                continue
            task = self.task_repo.get_task(submission.task_id)
            tasks.append(PortfolioTask(
                task_id=submission.task_id,
                title=task.title if task else f"task_{submission.task_id}",
                completed_at=submission.completed_at,
                points_awarded=submission.points_awarded,
            ))
        return tasks

    def _career_suggestions(self, student_id: int) -> list[PortfolioCareerSuggestion]:
        recommendations = self.student_service.list_student_career_recommendations(student_id)
        suggestions = []
        for rec in recommendations:
            career = self.market_repo.get_career(rec.career_id)
            suggestions.append(PortfolioCareerSuggestion(
                career_id=rec.career_id,
                career_title=career.title if career else f"career_{rec.career_id}",
                score=rec.score,
                rationale=rec.rationale,
            ))
        return suggestions

    def _suggested_next_tasks(self, student_id: int, limit: int = 5) -> list[PortfolioNextTask]:
        joined_task_ids = {s.task_id for s in self.task_repo.list_submissions(student_id=student_id)}
        approved_tasks = self.task_repo.list_tasks(review_status=TaskReviewStatus.APPROVED.value)
        candidates = [t for t in approved_tasks if t.id not in joined_task_ids]
        return [
            PortfolioNextTask(task_id=t.id, title=t.title, target_evidence_level=t.target_evidence_level.value)
            for t in candidates[:limit]
        ]

    def get_student_view(self, student_id: int) -> EPortfolioRead:
        student = self.student_service.get_student(student_id)
        setting = self.portfolio_repo.get_share_setting(student_id)
        try:
            profile = self.student_service.get_student_profile(student_id)
            headline = profile.headline
        except EntityNotFoundException:
            headline = None

        return EPortfolioRead(
            student_id=student_id,
            full_name=student.full_name,
            headline=headline,
            verified_skills=self._verified_skills(student_id),
            verified_evidence=self._verified_evidence(student_id),
            completed_tasks=self._completed_tasks(student_id),
            career_suggestions=self._career_suggestions(student_id),
            suggested_next_tasks=self._suggested_next_tasks(student_id),
            share_with_business=bool(setting and setting.share_with_business),
        )

    def get_business_view(self, student_id: int) -> EPortfolioBusinessView:
        student = self.student_service.get_student(student_id)
        setting = self.portfolio_repo.get_share_setting(student_id)
        if not setting or not setting.share_with_business:
            raise BusinessLogicException(
                f"Student {student_id} has not consented to share their ePortfolio with businesses",
                status_code=403,
            )
        try:
            profile = self.student_service.get_student_profile(student_id)
            headline = profile.headline
        except EntityNotFoundException:
            headline = None

        return EPortfolioBusinessView(
            student_id=student_id,
            full_name=student.full_name,
            headline=headline,
            verified_skills=self._verified_skills(student_id),
            selected_evidence=self._verified_evidence(student_id),
            selected_tasks=self._completed_tasks(student_id),
        )

    def update_share_setting(self, student_id: int, share_with_business: bool):
        self.student_service.get_student(student_id)  # 404s if missing
        return self.portfolio_repo.upsert_share_setting(student_id, share_with_business)
