"""Integration tests: real ORM models + a real TaskRepository against a mock
(in-memory SQLite) database, instead of the FakeRepo doubles used in
tests/unit. Exercises review_task's cascade to sub-tasks end-to-end through
actual SQL writes/reads, and the resulting effect on join_task."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from domains.task.repository import TaskRepository
from domains.task.service import TaskService
from domains.task.models import TaskReviewStatus, TaskRiskLevel


@pytest.fixture
def db():
    # StaticPool + single connection so the in-memory DB survives across the
    # multiple sessions/queries a real request lifecycle would use.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()


def make_service(db):
    # Same bypass as the unit tests: avoid constructing a real ChatbotService
    # (unrelated to review_task), but use the real TaskRepository/DB session.
    service = object.__new__(TaskService)
    service.repo = TaskRepository(db)
    return service


def make_root_and_subtasks(repo, n_subtasks=2, sub_risk_levels=None):
    company = repo.get_or_create_company({"name": "Acme", "slug": "acme"})
    root = repo.create_task({
        "title": "Root task",
        "company_id": company.id,
        "estimated_hours_min": 5,
        "estimated_hours_max": 10,
        "context": "Root context",
    })
    subs = []
    for i in range(n_subtasks):
        risk = (sub_risk_levels or {}).get(i, TaskRiskLevel.R0)
        subs.append(repo.create_task({
            "title": f"Sub task {i}",
            "company_id": company.id,
            "parent_task_id": root.id,
            "estimated_hours_min": 1,
            "estimated_hours_max": 2,
            "context": f"Sub context {i}",
            "risk_level": risk,
        }))
    return root, subs


def test_approving_root_task_propagates_to_subtasks_in_db(db):
    repo = TaskRepository(db)
    root, subs = make_root_and_subtasks(repo, n_subtasks=2)
    service = make_service(db)

    service.review_task(
        root.id, reviewer_id=1, decision=TaskReviewStatus.APPROVED,
        approved_complexity=None, approved_risk=None,
        approved_evidence_level=None, comment="looks good",
    )

    # Re-fetch from the DB (not the in-memory objects created above) to prove
    # the change was actually persisted, not just mutated in Python.
    assert repo.get_task(root.id).review_status == TaskReviewStatus.APPROVED
    for sub in subs:
        assert repo.get_task(sub.id).review_status == TaskReviewStatus.APPROVED


def test_rejecting_root_task_propagates_to_subtasks_in_db(db):
    repo = TaskRepository(db)
    root, subs = make_root_and_subtasks(repo, n_subtasks=2)
    service = make_service(db)

    service.review_task(
        root.id, reviewer_id=1, decision=TaskReviewStatus.REJECTED,
        approved_complexity=None, approved_risk=None,
        approved_evidence_level=None, comment="not ready",
    )

    assert repo.get_task(root.id).review_status == TaskReviewStatus.REJECTED
    for sub in subs:
        assert repo.get_task(sub.id).review_status == TaskReviewStatus.REJECTED


def test_approval_skips_subtask_with_blocked_risk_level_in_db(db):
    repo = TaskRepository(db)
    root, subs = make_root_and_subtasks(
        repo, n_subtasks=2, sub_risk_levels={1: TaskRiskLevel.R2}
    )
    service = make_service(db)

    service.review_task(
        root.id, reviewer_id=1, decision=TaskReviewStatus.APPROVED,
        approved_complexity=None, approved_risk=None,
        approved_evidence_level=None, comment=None,
    )

    assert repo.get_task(root.id).review_status == TaskReviewStatus.APPROVED
    assert repo.get_task(subs[0].id).review_status == TaskReviewStatus.APPROVED
    # R2 sub-task is left untouched: no Expert Reviewer exists in this MVP to
    # clear it, so the parent's approval must not silently unblock it.
    assert repo.get_task(subs[1].id).review_status == TaskReviewStatus.PENDING_MENTOR_APPROVAL


def test_reviewing_a_subtask_directly_does_not_affect_root_in_db(db):
    repo = TaskRepository(db)
    root, subs = make_root_and_subtasks(repo, n_subtasks=1)
    service = make_service(db)

    service.review_task(
        subs[0].id, reviewer_id=1, decision=TaskReviewStatus.APPROVED,
        approved_complexity=None, approved_risk=None,
        approved_evidence_level=None, comment=None,
    )

    assert repo.get_task(subs[0].id).review_status == TaskReviewStatus.APPROVED
    assert repo.get_task(root.id).review_status == TaskReviewStatus.PENDING_MENTOR_APPROVAL


def test_student_can_join_subtask_only_after_root_approval_cascades(db):
    repo = TaskRepository(db)
    root, subs = make_root_and_subtasks(repo, n_subtasks=1)
    service = make_service(db)

    with pytest.raises(Exception):
        service.join_task(subs[0].id, student_id=42)

    service.review_task(
        root.id, reviewer_id=1, decision=TaskReviewStatus.APPROVED,
        approved_complexity=None, approved_risk=None,
        approved_evidence_level=None, comment=None,
    )

    submission = service.join_task(subs[0].id, student_id=42)
    assert submission.task_id == subs[0].id
