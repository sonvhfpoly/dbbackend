import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.exceptions import BusinessLogicException
from domains.evidence.models import EvidenceStatus
from domains.evidence.schemas import EvidenceClaimCreate
from domains.evidence.service import EvidenceService
from domains.market.repository import MarketRepository
from domains.student.models import StudentCareerRecommendation
from domains.student.repository import StudentRepository
from domains.student.schemas import RecommendationGenerateRequest
from domains.student.service import StudentProfileService
from domains.task.models import CompletionActor, SubmissionStatus, TaskComplexity
from domains.task.repository import TaskRepository
from domains.task.service import TaskService
from domains.task.router import _schedule_career_refresh


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


def _verify_skill(db, student_id, skill_id, task, level="L2"):
    """Runs a skill through the real EvidenceClaim chain (AI_DRAFT ->
    STUDENT_REVIEWED -> PENDING_MENTOR -> VERIFIED) so a genuine
    StudentSkillProfile row exists — the recommendation engine now only
    trusts that as its skill signal, not Task.skills."""
    evidence_service = EvidenceService(db)
    claim = evidence_service.create_claim(EvidenceClaimCreate(
        student_id=student_id,
        skill_id=skill_id,
        task_id=task.id,
        claim=f"Demonstrated skill on task '{task.title}'",
        task_complexity=task.complexity_level.value,
        risk_level=task.risk_level.value,
        proposed_skill_level=level,
    ))
    evidence_service.student_review(claim.id)
    evidence_service.submit_to_mentor(claim.id)
    evidence_service.mentor_decide(claim.id, mentor_id=0, decision=EvidenceStatus.VERIFIED, comment="test")


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
    _verify_skill(db, student.id, python.id, task)
    _verify_skill(db, student.id, sql.id, task)
    return student, career, task


def test_llm_recommendation_uses_verified_skill_profile_and_upserts(db):
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


def test_generate_recommendations_falls_back_to_completed_task_skills(db):
    """A completed task's declared skills are usable as an explicitly
    unverified fallback when no StudentSkillProfile exists yet."""
    market = MarketRepository(db)
    tasks = TaskRepository(db)
    students = StudentRepository(db)

    python = market.get_or_create_skill("Python", category="technical")
    career = market.get_or_create_career("Công nghệ thông tin")
    market.get_or_create_job("Backend Developer", career.id, [python.id])
    student = students.create_student({"full_name": "Trần Bình", "email": "binh@example.com"})
    company = tasks.get_or_create_company({"name": "Acme", "slug": "acme-career-2"})
    task = tasks.create_task(
        {
            "title": "Viết script",
            "company_id": company.id,
            "estimated_hours_min": 1,
            "estimated_hours_max": 2,
            "competency_points": 10,
            "context": "ctx",
            "skill_ids": [python.id],
        }
    )
    submission = tasks.create_submission(task.id, student.id)
    tasks.update_submission(submission.id, status=SubmissionStatus.COMPLETED, completed_by=CompletionActor.MENTOR)

    chatbot = FakeChatbot(
        '{"recommendations":[{"career_id":%d,"score":0.62,'
        '"rationale":"Task đã hoàn thành có sử dụng Python.",'
        '"strengths":"Có trải nghiệm task Python","gaps":"Kỹ năng chưa được mentor xác thực",'
        '"next_steps":"Hoàn tất xác thực evidence"}]}' % career.id
    )
    service = make_recommendation_service(db, chatbot=chatbot)

    recommendations = service.generate_student_career_recommendations(
        student.id, RecommendationGenerateRequest(limit=5, persist=True)
    )

    assert len(recommendations) == 1
    prompt = chatbot.calls[0][0][1]["content"]
    assert '"known_skills": []' in prompt
    assert '"skill_name": "Python"' in prompt
    assert '"signal_source": "completed_task"' in prompt
    assert '"verified": false' in prompt


def test_generate_recommendations_falls_back_to_completed_task_when_skills_are_empty(db):
    market = MarketRepository(db)
    tasks = TaskRepository(db)
    students = StudentRepository(db)
    career = market.get_or_create_career("Công nghệ thông tin")
    student = students.create_student({"full_name": "Không Skill", "email": "no-skill@example.com"})
    company = tasks.get_or_create_company({"name": "No Skill Co", "slug": "no-skill-co"})
    task = tasks.create_task({
        "title": "Task không gắn skill",
        "company_id": company.id,
        "estimated_hours_min": 1,
        "estimated_hours_max": 2,
        "competency_points": 10,
        "context": "ctx",
    })
    submission = tasks.create_submission(task.id, student.id)
    tasks.update_submission(
        submission.id,
        status=SubmissionStatus.COMPLETED,
        completed_by=CompletionActor.MENTOR,
    )
    chatbot = FakeChatbot(
        '{"recommendations":[{"career_id":%d,"score":0.45,'
        '"rationale":"Nội dung task đã hoàn thành cho thấy tín hiệu ban đầu.",'
        '"strengths":"Đã hoàn thành task thực tế","gaps":"Chưa có skill được xác thực",'
        '"next_steps":"Bổ sung evidence và task có skill rõ ràng"}]}' % career.id
    )
    service = make_recommendation_service(db, chatbot=chatbot)

    recommendations = service.generate_student_career_recommendations(
        student.id,
        RecommendationGenerateRequest(limit=5, persist=True),
    )

    assert len(recommendations) == 1
    prompt = chatbot.calls[0][0][1]["content"]
    assert '"skills": []' in prompt
    assert '"title": "Task không gắn skill"' in prompt
    assert '"context": "ctx"' in prompt


def test_generate_recommendations_rejects_without_skills_or_completed_tasks(db):
    student = StudentRepository(db).create_student({
        "full_name": "Chưa Có Dữ Liệu",
        "email": "no-signal@example.com",
    })
    service = make_recommendation_service(db, chatbot=FakeChatbot("{}"))

    with pytest.raises(BusinessLogicException):
        service.generate_student_career_recommendations(
            student.id,
            RecommendationGenerateRequest(limit=5, persist=True),
        )

    assert service.chatbot.calls == []


def test_task_completion_schedules_background_recommendation_refresh(db):
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
    service = object.__new__(TaskService)
    service.repo = tasks
    background_tasks = BackgroundTasks()

    completed = service.mentor_review(submission.id, approved=True, feedback="Tốt")
    _schedule_career_refresh(background_tasks, completed)

    assert completed.status == SubmissionStatus.COMPLETED
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].args == (student.id,)
