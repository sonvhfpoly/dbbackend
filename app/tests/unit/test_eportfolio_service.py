import pytest
from datetime import datetime
from types import SimpleNamespace
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.eportfolio.service import EPortfolioService
from domains.task.models import SubmissionStatus

def make_service(student_service=None, evidence_repo=None, task_repo=None, market_repo=None, portfolio_repo=None):
    """EPortfolioService.__init__ opens a real DB session and 4 other real
    repos/services — bypass it and inject fakes directly, same pattern as
    test_task_service.py/test_market_service.py."""
    service = object.__new__(EPortfolioService)
    service.student_service = student_service or FakeStudentService()
    service.evidence_repo = evidence_repo or FakeEvidenceRepo()
    service.task_repo = task_repo or FakeTaskRepo()
    service.market_repo = market_repo or FakeMarketRepo()
    service.portfolio_repo = portfolio_repo or FakePortfolioRepo()
    return service

class FakeStudentService:
    def __init__(self, students=None, profiles=None, skill_profiles=None, career_recs=None):
        self.students = students or {}
        self.profiles = profiles or {}
        self.skill_profiles = skill_profiles or {}
        self.career_recs = career_recs or {}

    def get_student(self, student_id):
        return self.students.get(student_id, SimpleNamespace(id=student_id, full_name=f"Student {student_id}"))

    def get_student_profile(self, student_id):
        profile = self.profiles.get(student_id)
        if profile is None:
            raise EntityNotFoundException("StudentProfile", student_id)
        return profile

    def list_student_skill_profiles(self, student_id):
        return self.skill_profiles.get(student_id, [])

    def list_student_career_recommendations(self, student_id):
        return self.career_recs.get(student_id, [])

class FakeEvidenceRepo:
    def __init__(self, claims=None):
        self.claims = claims or {}

    def list_by_student(self, student_id, status=None):
        return self.claims.get(student_id, [])

class FakeTaskRepo:
    def __init__(self, submissions=None, tasks=None):
        self.submissions = submissions or {}
        self.tasks = tasks or {}

    def list_submissions(self, student_id=None, task_id=None):
        return self.submissions.get(student_id, [])

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def list_tasks(self, review_status=None):
        return []

class FakeMarketRepo:
    def __init__(self, skills=None, careers=None):
        self.skills = skills or {}
        self.careers = careers or {}

    def get_skill(self, skill_id):
        return self.skills.get(skill_id)

    def get_career(self, career_id):
        return self.careers.get(career_id)

class FakePortfolioRepo:
    def __init__(self, share_settings=None):
        self.share_settings = share_settings or {}

    def get_share_setting(self, student_id):
        return self.share_settings.get(student_id)

    def list_shared_student_ids(self):
        return [sid for sid, s in self.share_settings.items() if s.share_with_business]

# ---- list_candidates (requirements.md §32 "Ứng viên") ----

def test_list_candidates_only_returns_students_who_opted_into_sharing():
    portfolio_repo = FakePortfolioRepo(share_settings={
        1: SimpleNamespace(student_id=1, share_with_business=True),
        2: SimpleNamespace(student_id=2, share_with_business=False),
    })
    student_service = FakeStudentService(
        students={1: SimpleNamespace(id=1, full_name="An")},
        skill_profiles={1: [SimpleNamespace(skill_id=10, level=2, confidence=0.8, evidence_count=1)]},
    )
    evidence_repo = FakeEvidenceRepo(claims={
        1: [SimpleNamespace(id=1, skill_id=10, task_id=1, claim="x", proposed_skill_level="L2",
                             mentor_comment=None, decided_at=None, mentor_id=5)],
    })
    service = make_service(student_service=student_service, evidence_repo=evidence_repo, portfolio_repo=portfolio_repo)

    candidates = service.list_candidates()

    assert len(candidates) == 1
    assert candidates[0].student_id == 1
    assert candidates[0].skill_count == 1
    assert candidates[0].evidence_count == 1

def test_list_candidates_empty_when_nobody_has_shared():
    portfolio_repo = FakePortfolioRepo(share_settings={1: SimpleNamespace(student_id=1, share_with_business=False)})
    service = make_service(portfolio_repo=portfolio_repo)

    assert service.list_candidates() == []

# ---- get_business_view: consent gate + new fields (requirements.md §21) ----

def test_get_business_view_403s_without_consent():
    portfolio_repo = FakePortfolioRepo(share_settings={1: SimpleNamespace(student_id=1, share_with_business=False)})
    service = make_service(portfolio_repo=portfolio_repo)

    with pytest.raises(BusinessLogicException):
        service.get_business_view(1)

def test_get_business_view_includes_career_suggestions_mentor_id_and_joined_at():
    joined = datetime(2026, 1, 1)
    portfolio_repo = FakePortfolioRepo(share_settings={1: SimpleNamespace(student_id=1, share_with_business=True)})
    student_service = FakeStudentService(
        students={1: SimpleNamespace(id=1, full_name="An")},
        career_recs={1: [SimpleNamespace(career_id=99, score=0.9, rationale="fits")]},
    )
    market_repo = FakeMarketRepo(careers={99: SimpleNamespace(id=99, title="Data Analyst")})
    evidence_repo = FakeEvidenceRepo(claims={
        1: [SimpleNamespace(id=1, skill_id=10, task_id=1, claim="x", proposed_skill_level="L2",
                             mentor_comment="ok", decided_at=None, mentor_id=7)],
    })
    task_repo = FakeTaskRepo(
        submissions={1: [SimpleNamespace(task_id=1, status=SubmissionStatus.COMPLETED,
                                          completed_at=None, points_awarded=10, joined_at=joined)]},
        tasks={1: SimpleNamespace(title="Task A")},
    )
    service = make_service(
        student_service=student_service, market_repo=market_repo,
        evidence_repo=evidence_repo, task_repo=task_repo, portfolio_repo=portfolio_repo,
    )

    view = service.get_business_view(1)

    assert view.career_suggestions[0].career_title == "Data Analyst"
    assert view.selected_evidence[0].mentor_id == 7
    assert view.selected_tasks[0].joined_at == joined
