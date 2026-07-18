"""Integration tests for the Task<->Skill link (TaskSkill) and the
evidence-claim auto-draft on task completion:
- TaskService._ai_link_skills populates TaskSkill right after task creation.
- TaskService._draft_evidence_for_completion (called from complete_submission)
  drafts an AI_DRAFT EvidenceClaim per linked skill, using the task's own
  target_evidence_level as proposed_skill_level.
Uses a real in-memory SQLite DB + real repositories/services (same pattern as
test_task_review_integration.py) since this spans task/market/evidence."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from domains.task.repository import TaskRepository
from domains.task.service import TaskService
from domains.task.models import TaskComplexity, TaskReviewStatus, SubmissionStatus, CompletionActor
from domains.task.schemas import TaskCreate
from domains.market.repository import MarketRepository
from domains.evidence.repository import EvidenceRepository
from domains.evidence.models import EvidenceStatus


@pytest.fixture
def db():
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


class SequentialFakeChatbot:
    """Returns replies in order, one per .complete() call — needed here
    because a single create_task call can make more than one chatbot call
    (AI planning, then AI skill-linking), each expecting a different shape."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, messages, json_mode=False):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def make_service(db, chatbot):
    # Bypass TaskService.__init__ (which constructs a real ChatbotService) —
    # same convention as test_task_service.py's make_service — but keep real
    # repositories since this test spans task/market/evidence via real queries.
    service = object.__new__(TaskService)
    service.db = db
    service.repo = TaskRepository(db)
    service.market_repo = MarketRepository(db)
    service.chatbot = chatbot
    return service


def complete_full_lifecycle(service: TaskService, task_id: int, student_id: int):
    """Drives a task through review -> join -> submit -> mentor-review,
    returning the final submission. mentor_review completes the submission
    itself the moment it approves (mentor approval is always the final gate
    when a mentor is involved at all) — there's no separate complete_submission
    call needed/allowed afterward."""
    service.review_task(
        task_id, reviewer_id=1, decision=TaskReviewStatus.APPROVED,
        approved_complexity=None, approved_risk=None, approved_evidence_level=None, comment=None,
    )
    submission = service.join_task(task_id, student_id)
    service.submit_report(task_id, student_id, report_url="https://example.com/report")
    return service.mentor_review(submission.id, approved=True, feedback="Looks good")


# ---- AI skill-linking at creation time ----

def test_ai_link_skills_creates_task_skill_for_flat_root_task(db):
    chatbot = SequentialFakeChatbot([
        '{"complexity_level": "T1", "should_split": false, "sub_tasks": []}',
        '{"skills": ["Python"]}',
    ])
    service = make_service(db, chatbot)

    created = service.create_task(TaskCreate(
        title="Write a data pipeline script", company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, context="ctx",
    ))

    skill_ids = service.repo.get_task_skill_ids(created.id)
    assert len(skill_ids) == 1
    skill = service.market_repo.get_skill(skill_ids[0])
    assert skill.name == "Python"
    assert chatbot.calls == 2


def test_ai_link_skills_links_each_subtask_individually(db):
    chatbot = SequentialFakeChatbot([
        '{"complexity_level": "T2", "should_split": true, "sub_tasks": ['
        '{"title": "Sub 1", "context": "ctx 1", "estimated_hours_min": 1, "estimated_hours_max": 2, '
        '"competency_points": 10, "complexity_level": "T1"}]}',
        '{"skills": ["SQL"]}',  # skill-linking call for the one sub-task created above
    ])
    service = make_service(db, chatbot)

    created = service.create_task(TaskCreate(
        title="Broad data project", company_id=1,
        estimated_hours_min=10, estimated_hours_max=20, context="ctx",
    ))

    sub_tasks = service.repo.get_sub_tasks(created.id)
    assert len(sub_tasks) == 1
    # The root itself (now a container) should NOT get a skill link.
    assert service.repo.get_task_skill_ids(created.id) == []
    sub_skill_ids = service.repo.get_task_skill_ids(sub_tasks[0].id)
    assert len(sub_skill_ids) == 1
    assert service.market_repo.get_skill(sub_skill_ids[0]).name == "SQL"


def test_ai_link_skills_failure_does_not_block_task_creation(db):
    chatbot = SequentialFakeChatbot([
        '{"complexity_level": "T1", "should_split": false, "sub_tasks": []}',
        RuntimeError("provider down"),
    ])
    service = make_service(db, chatbot)

    created = service.create_task(TaskCreate(
        title="Some task", company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, context="ctx",
    ))

    assert created.id is not None
    assert service.repo.get_task_skill_ids(created.id) == []


def test_skip_ai_planning_skips_skill_linking_too(db):
    service = make_service(db, chatbot=None)  # would raise AttributeError if called

    created = service.create_task(TaskCreate(
        title="Flat task, no AI", company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, context="ctx",
        skip_ai_planning=True,
    ))

    assert service.repo.get_task_skill_ids(created.id) == []


# ---- auto-drafted evidence at completion time ----

def test_complete_submission_drafts_evidence_claim_for_linked_skill(db):
    chatbot = SequentialFakeChatbot([
        '{"complexity_level": "T1", "should_split": false, "sub_tasks": []}',
        '{"skills": ["Python"]}',
    ])
    service = make_service(db, chatbot)
    created = service.create_task(TaskCreate(
        title="Write a script", company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, context="ctx",
        target_evidence_level="L3",
    ))
    skill_id = service.repo.get_task_skill_ids(created.id)[0]

    complete_full_lifecycle(service, created.id, student_id=42)

    evidence_repo = EvidenceRepository(db)
    claims = evidence_repo.list_by_student(42)
    assert len(claims) == 1
    claim = claims[0]
    assert claim.skill_id == skill_id
    assert claim.task_id == created.id
    assert claim.status == EvidenceStatus.AI_DRAFT
    assert claim.proposed_skill_level == "L3"


def test_complete_submission_noop_when_no_linked_skills(db):
    service = make_service(db, chatbot=None)
    created = service.create_task(TaskCreate(
        title="Flat task, no AI", company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, context="ctx",
        skip_ai_planning=True,
    ))

    complete_full_lifecycle(service, created.id, student_id=7)

    assert EvidenceRepository(db).list_by_student(7) == []


def test_complete_submission_survives_evidence_draft_failure(db):
    service = make_service(db, chatbot=None)
    created = service.create_task(TaskCreate(
        title="Flat task, no AI", company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, context="ctx",
        skip_ai_planning=True,
    ))
    # Link to a skill_id that doesn't exist — evidence_service.create_claim
    # will raise EntityNotFoundException("Skill", ...) for it.
    service.repo.link_task_skill(created.id, 999999)

    submission = complete_full_lifecycle(service, created.id, student_id=8)

    assert submission.status == SubmissionStatus.COMPLETED  # not blocked
    assert EvidenceRepository(db).list_by_student(8) == []
