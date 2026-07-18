import pytest
from types import SimpleNamespace
from core.exceptions import BusinessLogicException
from domains.task.service import TaskService
from domains.task.models import TaskReviewStatus, TaskRiskLevel

def make_service(repo):
    """Same bypass-DB-session pattern as test_task_service.py — inject a fake
    repo directly since TaskService.__init__ normally opens a real session."""
    service = object.__new__(TaskService)
    service.repo = repo
    return service

def make_task(id, review_status=TaskReviewStatus.PENDING_MENTOR_APPROVAL, risk_level=TaskRiskLevel.R0, parent_task_id=None):
    return SimpleNamespace(id=id, review_status=review_status, risk_level=risk_level, parent_task_id=parent_task_id)

class FakeReviewRepo:
    def __init__(self, tasks=None):
        self.tasks = tasks or {}
        self.reviews = []

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def create_task_review(self, task_id, data):
        review = SimpleNamespace(id=len(self.reviews) + 1, task_id=task_id, **data)
        self.reviews.append(review)
        return review

    def update_task(self, task_id, **fields):
        task = self.tasks.get(task_id)
        if task is None:
            return None
        for key, value in fields.items():
            setattr(task, key, value)
        return task

    def list_task_reviews(self, task_id):
        return [r for r in self.reviews if r.task_id == task_id]

    def get_sub_tasks(self, parent_task_id):
        return [t for t in self.tasks.values() if t.parent_task_id == parent_task_id]

# ---- risk-level gate: requirements.md 4.2 "IF risk_level >= R2 THEN task cannot transition to APPROVED" ----

def test_review_task_blocks_approval_when_task_risk_is_r2():
    task = make_task(id=1, risk_level=TaskRiskLevel.R2)
    repo = FakeReviewRepo(tasks={1: task})
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.APPROVED,
                             approved_complexity=None, approved_risk=None,
                             approved_evidence_level=None, comment=None)

    assert task.review_status == TaskReviewStatus.PENDING_MENTOR_APPROVAL  # untouched

def test_review_task_blocks_approval_when_override_risk_is_r3():
    task = make_task(id=1, risk_level=TaskRiskLevel.R0)
    repo = FakeReviewRepo(tasks={1: task})
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.APPROVED,
                             approved_complexity=None, approved_risk="R3",
                             approved_evidence_level=None, comment=None)

def test_review_task_allows_approval_when_risk_is_r0():
    task = make_task(id=1, risk_level=TaskRiskLevel.R0)
    repo = FakeReviewRepo(tasks={1: task})
    service = make_service(repo)

    review = service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.APPROVED,
                                  approved_complexity=None, approved_risk=None,
                                  approved_evidence_level=None, comment="looks good")

    assert task.review_status == TaskReviewStatus.APPROVED
    assert review.decision == TaskReviewStatus.APPROVED

def test_review_task_rejects_pending_as_a_decision():
    task = make_task(id=1)
    repo = FakeReviewRepo(tasks={1: task})
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.PENDING_MENTOR_APPROVAL,
                             approved_complexity=None, approved_risk=None,
                             approved_evidence_level=None, comment=None)

def test_review_task_rejects_re_review_of_already_approved_task():
    task = make_task(id=1, review_status=TaskReviewStatus.APPROVED)
    repo = FakeReviewRepo(tasks={1: task})
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.REJECTED,
                             approved_complexity=None, approved_risk=None,
                             approved_evidence_level=None, comment=None)

def test_review_task_allows_re_review_after_need_more_info():
    task = make_task(id=1, review_status=TaskReviewStatus.NEED_MORE_INFO)
    repo = FakeReviewRepo(tasks={1: task})
    service = make_service(repo)

    service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.APPROVED,
                         approved_complexity=None, approved_risk=None,
                         approved_evidence_level=None, comment=None)

    assert task.review_status == TaskReviewStatus.APPROVED

# ---- join_task requires the task to already be APPROVED ----

def test_join_task_blocked_when_not_approved():
    task = make_task(id=1, review_status=TaskReviewStatus.PENDING_MENTOR_APPROVAL)
    repo = FakeReviewRepo(tasks={1: task})
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service.join_task(1, student_id=42)

# ---- root review propagates to sub-tasks (sub-tasks have no review UI of their own) ----

def test_review_task_approval_propagates_to_sub_tasks():
    root = make_task(id=1)
    sub1 = make_task(id=2, parent_task_id=1)
    sub2 = make_task(id=3, parent_task_id=1)
    repo = FakeReviewRepo(tasks={1: root, 2: sub1, 3: sub2})
    service = make_service(repo)

    service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.APPROVED,
                         approved_complexity=None, approved_risk=None,
                         approved_evidence_level=None, comment=None)

    assert sub1.review_status == TaskReviewStatus.APPROVED
    assert sub2.review_status == TaskReviewStatus.APPROVED

def test_review_task_rejection_propagates_to_sub_tasks():
    root = make_task(id=1)
    sub1 = make_task(id=2, parent_task_id=1)
    repo = FakeReviewRepo(tasks={1: root, 2: sub1})
    service = make_service(repo)

    service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.REJECTED,
                         approved_complexity=None, approved_risk=None,
                         approved_evidence_level=None, comment=None)

    assert sub1.review_status == TaskReviewStatus.REJECTED

def test_review_task_approval_skips_sub_task_with_blocked_risk():
    root = make_task(id=1, risk_level=TaskRiskLevel.R0)
    risky_sub = make_task(id=2, parent_task_id=1, risk_level=TaskRiskLevel.R2)
    repo = FakeReviewRepo(tasks={1: root, 2: risky_sub})
    service = make_service(repo)

    service.review_task(1, reviewer_id=5, decision=TaskReviewStatus.APPROVED,
                         approved_complexity=None, approved_risk=None,
                         approved_evidence_level=None, comment=None)

    assert risky_sub.review_status == TaskReviewStatus.PENDING_MENTOR_APPROVAL

def test_review_task_does_not_propagate_when_reviewing_a_sub_task_directly():
    root = make_task(id=1)
    sub1 = make_task(id=2, parent_task_id=1)
    repo = FakeReviewRepo(tasks={1: root, 2: sub1})
    service = make_service(repo)

    service.review_task(2, reviewer_id=5, decision=TaskReviewStatus.APPROVED,
                         approved_complexity=None, approved_risk=None,
                         approved_evidence_level=None, comment=None)

    assert root.review_status == TaskReviewStatus.PENDING_MENTOR_APPROVAL
