import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace
from core.exceptions import BusinessLogicException
from domains.task.service import TaskService
from domains.task.models import SubmissionStatus
from domains.task.schemas import TaskSubmissionRead
from domains.task import storage

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
        self.created_enterprise_reviews = []

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

    def create_enterprise_review(self, submission_id, data):
        review = SimpleNamespace(id=len(self.created_enterprise_reviews) + 1, submission_id=submission_id, **data)
        self.created_enterprise_reviews.append(review)
        return review

    def list_enterprise_reviews(self, submission_id):
        return self.created_enterprise_reviews

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

# ---- real upload path also enforces the 50MB/file cap (requirements.md §14) ----
# RegisterSubmissionFileRequest's size_bytes field only validates a caller-reported
# number on the metadata-only path; upload_submission_file controls the actual
# bytes, so it must check them itself instead of trusting the same schema.

def test_upload_submission_file_rejects_oversized_content():
    submission = make_submission(1, datetime.utcnow())
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)
    oversized = b"x" * (TaskService.MAX_FILE_SIZE_BYTES + 1)

    with pytest.raises(BusinessLogicException):
        service.upload_submission_file(1, "big.bin", "application/octet-stream", oversized)

    assert repo.created_files == []  # rejected before reaching GCS upload or registration

def test_upload_submission_file_allows_under_size_limit(monkeypatch):
    submission = make_submission(1, datetime.utcnow())
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)
    monkeypatch.setattr(storage, "upload_submission_file", lambda *a, **k: "https://storage.googleapis.com/bucket/x.txt")

    file = service.upload_submission_file(1, "x.txt", "text/plain", b"small content")

    assert file.file_url == "https://storage.googleapis.com/bucket/x.txt"

# ---- TaskSubmissionRead exposes files inline (BUS-11 "Files + review", MEN-13 "Fetch files") ----

def make_submission_file(id, submission_id, uploaded_at, file_name="x.txt", file_url="https://storage.googleapis.com/bucket/x.txt"):
    return SimpleNamespace(
        id=id, submission_id=submission_id, file_name=file_name, mime_type="text/plain",
        size_bytes=10, file_url=file_url, scan_status="PASSED", uploaded_at=uploaded_at,
    )

def make_full_submission(id, files, enterprise_reviews=None):
    now = datetime.utcnow()
    return SimpleNamespace(
        id=id, task_id=1, student_id=42, status=SubmissionStatus.SUBMITTED, joined_at=now,
        report_url=None, submitted_at=now, elapsed_seconds=None, student_reflection=None,
        auto_check_result=None, mentor_feedback=None, mentor_decision_at=None,
        completed_by=None, points_awarded=None, completed_at=None, files=files,
        enterprise_reviews=enterprise_reviews or [],
    )

def test_submission_read_serializes_files_in_order():
    older = make_submission_file(1, 1, datetime.utcnow() - timedelta(hours=1), file_name="a.txt")
    newer = make_submission_file(2, 1, datetime.utcnow(), file_name="b.txt")
    submission = make_full_submission(1, files=[older, newer])

    result = TaskSubmissionRead.model_validate(submission)

    assert [f.file_name for f in result.files] == ["a.txt", "b.txt"]
    assert result.files[0].file_url == older.file_url

def test_submission_read_defaults_files_to_empty_list():
    submission = make_full_submission(1, files=[])

    result = TaskSubmissionRead.model_validate(submission)

    assert result.files == []

# ---- EnterpriseReview (requirements.md BUS-12 — "Không thay Evidence") ----

def make_enterprise_review(id, submission_id, created_at, decision="ACCEPTED", comment=None):
    return SimpleNamespace(id=id, submission_id=submission_id, reviewed_by=500,
                            decision=decision, comment=comment, created_at=created_at)

def test_create_enterprise_review_never_touches_submission_status():
    submission = make_submission(1, datetime.utcnow(), status=SubmissionStatus.SUBMITTED)
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)

    review = service.create_enterprise_review(1, reviewed_by=500, decision="ACCEPTED", comment="Tot")

    assert review.decision == "ACCEPTED"
    assert repo.updated == {}  # update_submission was never called
    assert submission.status == SubmissionStatus.SUBMITTED  # unchanged

def test_list_enterprise_reviews_returns_created_history():
    submission = make_submission(1, datetime.utcnow())
    repo = FakeSubmissionRepo(submissions={(1, 42): submission})
    service = make_service(repo)
    service.create_enterprise_review(1, reviewed_by=500, decision="CHANGES_REQUESTED", comment="Thieu phan X")

    reviews = service.list_enterprise_reviews(1)

    assert len(reviews) == 1
    assert reviews[0].decision == "CHANGES_REQUESTED"

def test_submission_read_serializes_enterprise_reviews():
    review = make_enterprise_review(1, 1, datetime.utcnow(), decision="ACCEPTED")
    submission = make_full_submission(1, files=[], enterprise_reviews=[review])

    result = TaskSubmissionRead.model_validate(submission)

    assert len(result.enterprise_reviews) == 1
    assert result.enterprise_reviews[0].decision.value == "ACCEPTED"
    assert result.enterprise_reviews[0].reviewed_by == 500
