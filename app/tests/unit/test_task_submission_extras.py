import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace
from core.exceptions import BusinessLogicException
from domains.task.service import TaskService
from domains.task.models import SubmissionStatus

def make_service(repo):
    """Same bypass-DB-session pattern as test_task_service.py."""
    service = object.__new__(TaskService)
    service.repo = repo
    return service

def make_submission(id, joined_at, status=SubmissionStatus.JOINED):
    return SimpleNamespace(id=id, joined_at=joined_at, status=status)

class FakeSubmissionRepo:
    def __init__(self, submissions=None, files_count=0):
        self.submissions = submissions or {}
        self.updated = {}
        self._files_count = files_count
        self.created_files = []

    def get_latest_submission(self, task_id, student_id):
        return self.submissions.get((task_id, student_id))

    def update_submission(self, submission_id, **fields):
        self.updated = fields
        submission = next((s for s in self.submissions.values() if s.id == submission_id), None)
        if submission:
            for key, value in fields.items():
                setattr(submission, key, value)
        return submission

    def get_submission(self, submission_id):
        return next((s for s in self.submissions.values() if s.id == submission_id), None)

    def count_submission_files(self, submission_id):
        return self._files_count

    def create_submission_file(self, submission_id, data):
        file = SimpleNamespace(id=len(self.created_files) + 1, submission_id=submission_id, **data)
        self.created_files.append(file)
        return file

    def list_submission_files(self, submission_id):
        return self.created_files

# ---- elapsed_seconds + student_reflection on submit ----

def test_submit_report_computes_elapsed_seconds_from_joined_at():
    joined_at = datetime.utcnow() - timedelta(hours=3)
    submission = make_submission(1, joined_at)
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)

    service.submit_report(task_id=1, student_id=42, report_url="https://example.com/r")

    assert repo.updated["elapsed_seconds"] >= 3 * 3600 - 5  # ~3 hours, minus test-runtime slack
    assert isinstance(repo.updated["elapsed_seconds"], int)

def test_submit_report_stores_student_reflection():
    submission = make_submission(1, datetime.utcnow() - timedelta(hours=2))
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)
    reflection = {"challenge": "kho o cho X", "remaining_uncertainty": ["A"]}

    service.submit_report(task_id=1, student_id=42, report_url="https://example.com/r", student_reflection=reflection)

    assert repo.updated["student_reflection"] == reflection

def test_submit_report_reflection_defaults_to_none():
    submission = make_submission(1, datetime.utcnow())
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)

    service.submit_report(task_id=1, student_id=42, report_url="https://example.com/r")

    assert repo.updated["student_reflection"] is None

def test_submit_report_clears_stale_review_state_on_resubmit():
    """Regression test: resubmitting after MENTOR_REJECTED/AUTO_CHECK_FAILED
    must clear the previous cycle's mentor_feedback/mentor_decision_at/
    auto_check_result — otherwise the new (unreviewed) submission looks like
    it already has a mentor decision from the rejected attempt."""
    submission = make_submission(1, datetime.utcnow() - timedelta(hours=1), status=SubmissionStatus.MENTOR_REJECTED)
    submission.mentor_feedback = "Thieu phan ket luan"
    submission.mentor_decision_at = datetime.utcnow() - timedelta(minutes=30)
    submission.auto_check_result = {"passed": False, "reason": "report_url missing"}
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)

    service.submit_report(task_id=1, student_id=42, report_url="https://example.com/r2")

    assert repo.updated["mentor_feedback"] is None
    assert repo.updated["mentor_decision_at"] is None
    assert repo.updated["auto_check_result"] is None
    assert repo.updated["status"] == SubmissionStatus.SUBMITTED

# ---- submission file limits (requirements.md §14: max 10 files/submission) ----

def test_register_submission_file_rejects_when_at_max():
    submission = make_submission(1, datetime.utcnow())
    repo = FakeSubmissionRepo(submissions={(1, 42): submission}, files_count=10)
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service.register_submission_file(1, {"file_name": "x.txt", "mime_type": "text/plain", "size_bytes": 10, "file_url": "u"})

def test_register_submission_file_allows_when_under_max():
    submission = make_submission(1, datetime.utcnow())
    repo = FakeSubmissionRepo(submissions={(1, 42): submission}, files_count=9)
    service = make_service(repo)

    file = service.register_submission_file(1, {"file_name": "x.txt", "mime_type": "text/plain", "size_bytes": 10, "file_url": "u"})

    assert file.scan_status == "PASSED"  # placeholder scan, no real scanner integrated yet
