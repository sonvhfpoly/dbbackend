import pytest
from types import SimpleNamespace
from core.exceptions import BusinessLogicException
from domains.evidence.service import EvidenceService
from domains.evidence.models import EvidenceStatus

def make_service(repo, applied=None):
    """Bypass EvidenceService.__init__ (which opens a real DB session via
    EvidenceRepository/TaskRepository/MarketRepository) — inject a fake
    evidence repo directly, same pattern used in test_task_service.py."""
    service = object.__new__(EvidenceService)
    service.repo = repo
    if applied is not None:
        service._apply_to_skill_profile = lambda claim: applied.append(claim)
    return service

def make_claim(id, status=EvidenceStatus.AI_DRAFT, proposed_skill_level="L2"):
    return SimpleNamespace(
        id=id, student_id=1, skill_id=2, task_id=3, claim="did the thing",
        status=status, proposed_skill_level=proposed_skill_level,
        mentor_id=None, mentor_comment=None, decided_at=None,
    )

class FakeEvidenceRepo:
    def __init__(self, claims=None):
        self.claims = claims or {}

    def get_claim(self, claim_id):
        return self.claims.get(claim_id)

    def update_claim(self, claim_id, **fields):
        claim = self.claims.get(claim_id)
        if claim is None:
            return None
        for key, value in fields.items():
            setattr(claim, key, value)
        return claim

# ---- state machine: AI_DRAFT -> STUDENT_REVIEWED -> PENDING_MENTOR -> {VERIFIED, NEED_MORE_EVIDENCE, REJECTED} ----

def test_student_review_transitions_from_ai_draft():
    claim = make_claim(1, status=EvidenceStatus.AI_DRAFT)
    service = make_service(FakeEvidenceRepo({1: claim}))

    service.student_review(1)

    assert claim.status == EvidenceStatus.STUDENT_REVIEWED

def test_student_review_rejects_wrong_status():
    claim = make_claim(1, status=EvidenceStatus.PENDING_MENTOR)
    service = make_service(FakeEvidenceRepo({1: claim}))

    with pytest.raises(BusinessLogicException):
        service.student_review(1)

def test_submit_to_mentor_transitions_from_student_reviewed():
    claim = make_claim(1, status=EvidenceStatus.STUDENT_REVIEWED)
    service = make_service(FakeEvidenceRepo({1: claim}))

    service.submit_to_mentor(1)

    assert claim.status == EvidenceStatus.PENDING_MENTOR

def test_submit_to_mentor_rejects_ai_draft():
    claim = make_claim(1, status=EvidenceStatus.AI_DRAFT)
    service = make_service(FakeEvidenceRepo({1: claim}))

    with pytest.raises(BusinessLogicException):
        service.submit_to_mentor(1)

def test_mentor_decide_rejects_when_not_pending_mentor():
    claim = make_claim(1, status=EvidenceStatus.AI_DRAFT)
    service = make_service(FakeEvidenceRepo({1: claim}))

    with pytest.raises(BusinessLogicException):
        service.mentor_decide(1, mentor_id=9, decision=EvidenceStatus.VERIFIED, comment=None)

def test_mentor_decide_rejects_ai_draft_as_a_decision():
    claim = make_claim(1, status=EvidenceStatus.PENDING_MENTOR)
    service = make_service(FakeEvidenceRepo({1: claim}))

    with pytest.raises(BusinessLogicException):
        service.mentor_decide(1, mentor_id=9, decision=EvidenceStatus.AI_DRAFT, comment=None)

def test_mentor_decide_verified_updates_skill_profile():
    claim = make_claim(1, status=EvidenceStatus.PENDING_MENTOR)
    applied = []
    service = make_service(FakeEvidenceRepo({1: claim}), applied=applied)

    service.mentor_decide(1, mentor_id=9, decision=EvidenceStatus.VERIFIED, comment="great work")

    assert claim.status == EvidenceStatus.VERIFIED
    assert claim.mentor_id == 9
    assert applied == [claim]  # human-in-the-loop step actually ran

def test_mentor_decide_rejected_does_not_touch_skill_profile():
    claim = make_claim(1, status=EvidenceStatus.PENDING_MENTOR)
    applied = []
    service = make_service(FakeEvidenceRepo({1: claim}), applied=applied)

    service.mentor_decide(1, mentor_id=9, decision=EvidenceStatus.REJECTED, comment="not enough proof")

    assert claim.status == EvidenceStatus.REJECTED
    assert applied == []

def test_mentor_decide_need_more_evidence_does_not_touch_skill_profile():
    claim = make_claim(1, status=EvidenceStatus.PENDING_MENTOR)
    applied = []
    service = make_service(FakeEvidenceRepo({1: claim}), applied=applied)

    service.mentor_decide(1, mentor_id=9, decision=EvidenceStatus.NEED_MORE_EVIDENCE, comment=None)

    assert claim.status == EvidenceStatus.NEED_MORE_EVIDENCE
    assert applied == []
