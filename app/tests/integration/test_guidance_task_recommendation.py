"""Integration tests for GuidanceService.generate_recommendations' new
behavior: recommend the student's next open Task toward a target Job (skill
gap vs JobSkill), instead of persisting an EducationPath pick. Uses a real
in-memory SQLite DB + real repositories (same pattern as
tests/integration/test_task_review_integration.py) since the service queries
StudentSkillProfile directly via self.db.query(...)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.guidance.repository import GuidanceRepository
from domains.guidance.service import GuidanceService
from domains.market.repository import MarketRepository
from domains.student.repository import StudentRepository
from domains.student.models import StudentSkillProfile
from domains.task.repository import TaskRepository
from domains.task.models import TaskComplexity, TaskReviewStatus


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


class FakeChatbot:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def complete(self, messages, json_mode=False):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def make_service(db, chatbot=None):
    # Bypass GuidanceService.__init__ (which constructs a real ChatbotService)
    # so tests never risk a real network call — same convention as
    # test_task_service.py's make_service.
    service = object.__new__(GuidanceService)
    service.db = db
    service.repo = GuidanceRepository(db)
    service.student_repo = StudentRepository(db)
    service.market_repo = MarketRepository(db)
    service.task_repo = TaskRepository(db)
    service.chatbot = chatbot or FakeChatbot(AssertionError("chatbot should not be called on the rule-based path"))
    return service


def make_student(student_repo, email="student@example.com"):
    return student_repo.create_student({"full_name": "Test Student", "email": email})


def make_task(task_repo, company_id, complexity, parent_task_id=None, title=None):
    task = task_repo.create_task({
        "title": title or f"Task {complexity.value}",
        "company_id": company_id,
        "parent_task_id": parent_task_id,
        "estimated_hours_min": 1,
        "estimated_hours_max": 2,
        "context": "ctx",
        "complexity_level": complexity,
    })
    return task_repo.update_task(task.id, review_status=TaskReviewStatus.APPROVED)


def make_job_with_skills(market_repo, skill_names):
    career = market_repo.get_or_create_career("Data")
    skill_ids = [market_repo.get_or_create_skill(name, category="general").id for name in skill_names]
    return market_repo.get_or_create_job("Data Analyst", career.id, skill_ids)


# ---- rule-based skill-gap path ----

def test_recommends_task_at_matching_complexity_band(db):
    task_repo = TaskRepository(db)
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    company = task_repo.get_or_create_company({"name": "Acme", "slug": "acme"})

    t1 = make_task(task_repo, company.id, TaskComplexity.T1)
    t2 = make_task(task_repo, company.id, TaskComplexity.T2)
    t3 = make_task(task_repo, company.id, TaskComplexity.T3)

    job = make_job_with_skills(market_repo, ["SQL", "Python"])
    student = make_student(student_repo)
    sql_skill = market_repo.get_or_create_skill("SQL", category="general")
    db.add(StudentSkillProfile(student_id=student.id, skill_id=sql_skill.id, level=3))
    db.commit()

    service = make_service(db)
    result = service.generate_recommendations(student.id, job.id, count=3)

    # matched=1/2 -> match_ratio=0.5 -> T2 band
    assert len(result) == 1
    assert result[0]["task_id"] == t2.id
    assert "1/2" in result[0]["reasoning_explanation"]


def test_falls_back_to_any_candidate_when_band_is_empty(db):
    task_repo = TaskRepository(db)
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    company = task_repo.get_or_create_company({"name": "Acme", "slug": "acme"})

    t1 = make_task(task_repo, company.id, TaskComplexity.T1)

    job = make_job_with_skills(market_repo, ["SQL", "Python", "Excel"])
    student = make_student(student_repo)
    for name in ["SQL", "Python", "Excel"]:
        skill = market_repo.get_or_create_skill(name, category="general")
        db.add(StudentSkillProfile(student_id=student.id, skill_id=skill.id, level=5))
    db.commit()

    service = make_service(db)
    # match_ratio=1.0 -> T3 band, but no T3 task exists -> falls back to all candidates
    result = service.generate_recommendations(student.id, job.id, count=3)

    assert len(result) == 1
    assert result[0]["task_id"] == t1.id


# ---- cold start: no skill signal at all -> LLM fallback ----

def test_cold_start_uses_llm_when_student_has_no_skills(db):
    task_repo = TaskRepository(db)
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    company = task_repo.get_or_create_company({"name": "Acme", "slug": "acme"})
    t1 = make_task(task_repo, company.id, TaskComplexity.T1)

    job = make_job_with_skills(market_repo, ["SQL"])
    student = make_student(student_repo)  # no StudentSkill/StudentSkillProfile rows at all

    reply = f'[{{"task_id": {t1.id}, "reasoning_explanation": "Nhiem vu khoi dau phu hop"}}]'
    chatbot = FakeChatbot(reply)
    service = make_service(db, chatbot=chatbot)

    result = service.generate_recommendations(student.id, job.id, count=3)

    assert chatbot.calls == 1
    assert result == [{
        "task_id": t1.id,
        "title": t1.title,
        "complexity_level": TaskComplexity.T1,
        "target_evidence_level": t1.target_evidence_level,
        "competency_points": t1.competency_points,
        "company_id": company.id,
        "reasoning_explanation": "Nhiem vu khoi dau phu hop",
    }]


def test_cold_start_falls_back_deterministically_when_llm_fails(db):
    task_repo = TaskRepository(db)
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    company = task_repo.get_or_create_company({"name": "Acme", "slug": "acme"})
    t1 = make_task(task_repo, company.id, TaskComplexity.T1)
    t2 = make_task(task_repo, company.id, TaskComplexity.T2)

    job = make_job_with_skills(market_repo, ["SQL"])
    student = make_student(student_repo)

    chatbot = FakeChatbot(Exception("provider down"))
    service = make_service(db, chatbot=chatbot)

    result = service.generate_recommendations(student.id, job.id, count=3)

    # No exception propagates; deterministic fallback prefers the lowest complexity first.
    assert result[0]["task_id"] == t1.id
    assert result[1]["task_id"] == t2.id


def test_cold_start_when_job_has_no_configured_skills(db):
    task_repo = TaskRepository(db)
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    company = task_repo.get_or_create_company({"name": "Acme", "slug": "acme"})
    t1 = make_task(task_repo, company.id, TaskComplexity.T1)

    career = market_repo.get_or_create_career("Data")
    job = market_repo.get_or_create_job("Analyst With No Skills", career.id, [])
    student = make_student(student_repo)
    sql_skill = market_repo.get_or_create_skill("SQL", category="general")
    db.add(StudentSkillProfile(student_id=student.id, skill_id=sql_skill.id, level=3))
    db.commit()

    chatbot = FakeChatbot(f'[{{"task_id": {t1.id}, "reasoning_explanation": "ok"}}]')
    service = make_service(db, chatbot=chatbot)

    service.generate_recommendations(student.id, job.id, count=3)

    assert chatbot.calls == 1  # required_skill_ids is empty -> cold start, even though the student has skills


# ---- candidate filtering ----

def test_excludes_tasks_the_student_already_started(db):
    task_repo = TaskRepository(db)
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    company = task_repo.get_or_create_company({"name": "Acme", "slug": "acme"})
    t1 = make_task(task_repo, company.id, TaskComplexity.T1)
    t1b = make_task(task_repo, company.id, TaskComplexity.T1, title="Task T1 second")

    job = make_job_with_skills(market_repo, ["SQL"])
    student = make_student(student_repo)
    task_repo.create_submission(t1.id, student.id)

    chatbot = FakeChatbot(f'[{{"task_id": {t1b.id}, "reasoning_explanation": "ok"}}]')
    service = make_service(db, chatbot=chatbot)

    result = service.generate_recommendations(student.id, job.id, count=3)

    assert all(r["task_id"] != t1.id for r in result)


def test_excludes_parent_tasks_that_have_subtasks(db):
    task_repo = TaskRepository(db)
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    company = task_repo.get_or_create_company({"name": "Acme", "slug": "acme"})
    root = make_task(task_repo, company.id, TaskComplexity.T1, title="Root with children")
    sub = make_task(task_repo, company.id, TaskComplexity.T1, parent_task_id=root.id, title="Sub task")

    job = make_job_with_skills(market_repo, ["SQL"])
    student = make_student(student_repo)

    chatbot = FakeChatbot(f'[{{"task_id": {sub.id}, "reasoning_explanation": "ok"}}]')
    service = make_service(db, chatbot=chatbot)

    result = service.generate_recommendations(student.id, job.id, count=3)

    assert all(r["task_id"] != root.id for r in result)
    assert any(r["task_id"] == sub.id for r in result)


def test_raises_when_no_open_tasks_exist(db):
    market_repo = MarketRepository(db)
    student_repo = StudentRepository(db)
    job = make_job_with_skills(market_repo, ["SQL"])
    student = make_student(student_repo)

    service = make_service(db)

    with pytest.raises(BusinessLogicException):
        service.generate_recommendations(student.id, job.id, count=3)


def test_unknown_student_404s(db):
    market_repo = MarketRepository(db)
    job = make_job_with_skills(market_repo, ["SQL"])
    service = make_service(db)

    with pytest.raises(EntityNotFoundException):
        service.generate_recommendations(999, job.id, count=3)


def test_unknown_job_404s(db):
    student_repo = StudentRepository(db)
    student = make_student(student_repo)
    service = make_service(db)

    with pytest.raises(EntityNotFoundException):
        service.generate_recommendations(student.id, 999, count=3)
