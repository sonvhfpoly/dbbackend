from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.market.repository import MarketRepository
from domains.student.repository import StudentRepository
from domains.student.service import StudentProfileService
from domains.student.schemas import StudentSkillEventCreate
from domains.student.constants import SkillEventType, SourceService
from domains.task.repository import TaskRepository
from .repository import EvidenceRepository
from .models import EvidenceStatus
from .schemas import EvidenceClaimCreate

# Maps EvidenceLevel strings ("L1".."L5") to the 1-5 integer scale
# StudentSkillProfile.level already uses (see domains/student/models.py).
_SKILL_LEVEL_TO_INT = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}

class EvidenceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EvidenceRepository(db)
        self.task_repo = TaskRepository(db)
        self.market_repo = MarketRepository(db)

    def create_claim(self, payload: EvidenceClaimCreate):
        task = self.task_repo.get_task(payload.task_id)
        if task is None:
            raise EntityNotFoundException("Task", payload.task_id)
        if self.market_repo.get_skill(payload.skill_id) is None:
            raise EntityNotFoundException("Skill", payload.skill_id)
        return self.repo.create_claim(payload.model_dump())

    def _get_claim_or_404(self, claim_id: int):
        claim = self.repo.get_claim(claim_id)
        if claim is None:
            raise EntityNotFoundException("EvidenceClaim", claim_id)
        return claim

    def _require_status(self, claim, allowed: set) -> None:
        if claim.status not in allowed:
            allowed_names = ", ".join(s.value for s in allowed)
            raise BusinessLogicException(
                f"EvidenceClaim {claim.id} is '{claim.status.value}', expected one of: {allowed_names}"
            )

    def student_review(self, claim_id: int):
        claim = self._get_claim_or_404(claim_id)
        self._require_status(claim, {EvidenceStatus.AI_DRAFT})
        return self.repo.update_claim(claim_id, status=EvidenceStatus.STUDENT_REVIEWED)

    def submit_to_mentor(self, claim_id: int):
        claim = self._get_claim_or_404(claim_id)
        self._require_status(claim, {EvidenceStatus.STUDENT_REVIEWED})
        return self.repo.update_claim(claim_id, status=EvidenceStatus.PENDING_MENTOR)

    def mentor_decide(self, claim_id: int, mentor_id: int, decision: EvidenceStatus, comment: Optional[str]):
        claim = self._get_claim_or_404(claim_id)
        self._require_status(claim, {EvidenceStatus.PENDING_MENTOR})
        if decision not in {EvidenceStatus.VERIFIED, EvidenceStatus.NEED_MORE_EVIDENCE, EvidenceStatus.REJECTED}:
            raise BusinessLogicException("decision must be VERIFIED, NEED_MORE_EVIDENCE, or REJECTED")

        updated = self.repo.update_claim(
            claim_id,
            status=decision,
            mentor_id=mentor_id,
            mentor_comment=comment,
            decided_at=datetime.utcnow(),
        )

        if decision == EvidenceStatus.VERIFIED:
            self._apply_to_skill_profile(updated)

        return updated

    def _apply_to_skill_profile(self, claim) -> None:
        """A verified claim is the human decision point (requirements.md
        section 29: 'AI proposes Evidence -> Mentor verifies') that actually
        moves the needle on a student's skill profile — recorded as a skill
        event, same mechanism the student domain already uses for any other
        evidence source (see StudentProfileService.create_student_skill_event)."""
        target_level = _SKILL_LEVEL_TO_INT.get(claim.proposed_skill_level)
        if target_level is None:
            return

        skill_service = StudentProfileService(self.db)
        existing_profiles = {
            p.skill_id: p for p in skill_service.list_student_skill_profiles(claim.student_id)
        }
        current_level = existing_profiles[claim.skill_id].level if claim.skill_id in existing_profiles else 0
        level_delta = max(-5, min(5, target_level - current_level))

        skill_service.create_student_skill_event(
            claim.student_id,
            StudentSkillEventCreate(
                skill_id=claim.skill_id,
                event_type=SkillEventType.MENTOR_FEEDBACK,
                source_service=SourceService.STUDENT_SERVICE,
                source_ref=f"evidence_claim:{claim.id}",
                title=f"Evidence verified for task {claim.task_id}",
                description=claim.claim,
                level_delta=level_delta,
                confidence=0.8,
            ),
        )

    def get_claim(self, claim_id: int):
        return self._get_claim_or_404(claim_id)

    def list_by_student(self, student_id: int, status: Optional[str] = None):
        return self.repo.list_by_student(student_id, status=status)

    def list_pending_mentor(self):
        return self.repo.list_pending_mentor()
