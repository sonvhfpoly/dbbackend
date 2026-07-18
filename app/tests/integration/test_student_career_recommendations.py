import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from domains.market.repository import MarketRepository
from domains.student.models import StudentCareerRecommendation
from domains.student.repository import StudentRepository
from domains.student.schemas import RecommendationGenerateRequest
from domains.student.service import StudentProfileService
from domains.task.models import CompletionActor, SubmissionStatus, TaskComplexity
from domains.task.repository import TaskRepository
from domains.task.service import TaskService


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
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = []

    def complete(self, messages, json_mode=False):
        self.calls.append((messages, json_mode))
        return self.reply


def make_recommendation_service(db, chatbot):
    service = object.__new__(StudentProfileService)
    service.db = db
    service.student_repo = StudentRepository(db)
    service.market_repo = MarketRepository(db)
    service.chatbot = chatbot
    return service


def seed_completed_task(db):
    market = MarketRepository(db)
    tasks = TaskRepository(db)
    students = StudentRepository(db)

    python = market.get_or_create_skill("Python", category="technical")
    sql = market.get_or_create_skill("SQL", category="data")
    career = market.get_or_create_career("Công nghệ thông tin")
    market.get_or_create_job("Backend Developer", career.id, [python.id, sql.id])
    student = students.create_student(
        {"full_name": "Nguyễn Minh", "email": "minh@example.com"}
    )
    company = tasks.get_or_create_company({"name": "Acme", "slug": "acme-career"})
    task = tasks.create_task(
        {
            "title": "Xây dựng REST API",
            "company_id": company.id,
            "estimated_hours_min": 3,
            "estimated_hours_max": 6,
            "competency_points": 30,
            "context": "Thiết kế API và truy vấn cơ sở dữ liệu",
            "complexity_level": TaskComplexity.T2,
            "skill_ids": [python.id, sql.id],
        }
    )
    submission = tasks.create_submission(task.id, student.id)
    tasks.update_submission(
        submission.id,
        status=SubmissionStatus.COMPLETED,
        completed_by=CompletionActor.MENTOR,
    )
    return student, career, task


def test_llm_recommendation_uses_completed_task_skills_and_upserts(db):
    student, career, task = seed_completed_task(db)
    chatbot = FakeChatbot(
        '{"recommendations":[{"career_id":%d,"score":0.82,'
        '"rationale":"Task REST API cho thấy nền tảng phù hợp.",'
        '"strengths":"Python và SQL","gaps":"Cần thêm kinh nghiệm triển khai",'
        '"next_steps":"Làm task triển khai dịch vụ"}]}' % career.id
    )
    service = make_recommendation_service(db, chatbot)

    first = service.generate_student_career_recommendations(
        student.id, RecommendationGenerateRequest(limit=5, persist=True)
    )

    assert len(first) == 1
    assert first[0].career_title == career.title
    assert first[0].generated_by == "llm_v1"
    assert chatbot.calls[0][1] is True
    sent_prompt = chatbot.calls[0][0][1]["content"]
    assert task.title in sent_prompt
    assert "Python" in sent_prompt
    assert "Backend Developer" in sent_prompt

    chatbot.reply = (
        '{"recommendations":[{"career_id":%d,"score":0.91,'
        '"rationale":"Nhiều bằng chứng hơn.","strengths":"Python",'
        '"gaps":"Cloud","next_steps":"Học cloud"}]}' % career.id
    )
    second = service.generate_student_career_recommendations(
        student.id, RecommendationGenerateRequest(limit=5, persist=True)
    )

    assert second[0].id == first[0].id
    assert second[0].score == 0.91
    assert db.query(StudentCareerRecommendation).count() == 1


def test_task_completion_triggers_recommendation_refresh(db, monkeypatch):
    student, _, task = seed_completed_task(db)
    tasks = TaskRepository(db)
    # Use a fresh submitted row so mentor_review performs the terminal transition.
    second_task = tasks.create_task(
        {
            "title": "Review API",
            "company_id": task.company_id,
            "estimated_hours_min": 1,
            "estimated_hours_max": 2,
            "competency_points": 10,
            "context": "Review",
        }
    )
    submission = tasks.create_submission(second_task.id, student.id)
    tasks.update_submission(submission.id, status=SubmissionStatus.SUBMITTED)
    calls = []

    def fake_generate(self, student_id, payload):
        calls.append((student_id, payload.persist))
        return []

    monkeypatch.setattr(
        StudentProfileService,
        "generate_student_career_recommendations",
        fake_generate,
    )
    service = object.__new__(TaskService)
    service.repo = tasks

    completed = service.mentor_review(submission.id, approved=True, feedback="Tốt")

    assert completed.status == SubmissionStatus.COMPLETED
    assert calls == [(student.id, True)]
