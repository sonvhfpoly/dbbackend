from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session
from typing import List, Optional
from core.database import get_db
from core.config import settings
from .schemas import (
    CompanyCreate, CompanyRead,
    TaskCreate, TaskRead,
    JoinTaskRequest, SubmitReportRequest, MentorReviewRequest,
    CompleteSubmissionRequest, ScoreCriterionRequest,
    TaskSubmissionRead, TaskSubmissionScoreRead, TaskProgressRead,
    TaskComplexity, TaskReviewRequest, TaskReviewRead, TaskReviewStatus,
    RegisterSubmissionFileRequest, TaskSubmissionFileRead,
    SetTaskSkillsRequest,
)
from .service import TaskService
from .models import SubmissionStatus
from domains.student.background import refresh_career_recommendations

router = APIRouter(prefix="/tasks", tags=["Task Marketplace"])


def _schedule_career_refresh(background_tasks: BackgroundTasks, submission) -> None:
    if submission.status == SubmissionStatus.COMPLETED:
        background_tasks.add_task(
            refresh_career_recommendations,
            submission.student_id,
        )

@router.post("/companies", response_model=CompanyRead, summary="Register a company sponsoring tasks")
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    return TaskService(db).create_company(company)

# No trailing slash — same reasoning as /submissions and /pending-approval
# below: registered before the generic /{task_id}, but a request that omits
# the trailing slash (e.g. GET /tasks/companies) wouldn't match a "/companies/"
# pattern at all and would silently fall through to /{task_id} instead,
# turning "companies" into a 422 "not a valid integer" on task_id.
@router.get("/companies", response_model=List[CompanyRead], summary="List companies")
def list_companies(db: Session = Depends(get_db)):
    return TaskService(db).list_companies()

@router.post("/", response_model=TaskRead, summary="Create a task (or a sub-task, via parent_task_id)")
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    return TaskService(db).create_task(task)

@router.get("/", response_model=List[TaskRead], summary="List root tasks, optionally filtered")
def list_tasks(
    complexity_level: Optional[TaskComplexity] = None,
    company_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return TaskService(db).list_tasks(complexity_level=complexity_level.value if complexity_level else None, company_id=company_id)

@router.get(
    "/submissions",
    response_model=List[TaskSubmissionRead],
    summary="List submissions, optionally filtered by student and/or task",
    description="Omit both filters to list every submission across the platform.",
)
def list_submissions(
    student_id: Optional[int] = None,
    task_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return TaskService(db).list_submissions(task_id=task_id, student_id=student_id)

# Registered before the generic /{task_id} below: Starlette matches routes in
# registration order, and /{task_id} (a single path segment, no int converter
# in the path template) would otherwise swallow the literal "/submissions"
# path too — the type-mismatch 422 happens only after routing already picked
# this route, so it never falls through to the real one below it.
@router.get(
    "/pending-approval",
    response_model=List[TaskRead],
    summary="List root tasks awaiting (or needing more info for) mentor approval",
)
def list_pending_approval_tasks(company_id: Optional[int] = None, db: Session = Depends(get_db)):
    return TaskService(db).list_tasks(company_id=company_id, review_status=TaskReviewStatus.PENDING_MENTOR_APPROVAL.value)

@router.get("/{task_id}", response_model=TaskRead, summary="Get a task's detail, including its sub-tasks")
def get_task(task_id: int, db: Session = Depends(get_db)):
    return TaskService(db).get_task(task_id)

@router.put(
    "/{task_id}/skills",
    response_model=TaskRead,
    summary="Replace the skills exercised by a task",
)
def set_task_skills(task_id: int, request: SetTaskSkillsRequest, db: Session = Depends(get_db)):
    return TaskService(db).set_task_skills(task_id, request.skill_ids)

@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    description="Blocked if the task (or a sub-task) has evidence claims recorded against it — deleting a task "
                "never cascades into evidence. If it has sub-tasks or submissions, pass force=true to delete "
                "them along with the task; otherwise the request is rejected.",
)
def delete_task(task_id: int, force: bool = False, db: Session = Depends(get_db)):
    TaskService(db).delete_task(task_id, force=force)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post(
    "/{task_id}/review",
    response_model=TaskReviewRead,
    summary="Mentor approves, rejects, or requests more info on a Task itself",
    description="Distinct from mentor-review of a submission: this gates whether students can join the task at all. "
                "APPROVED is rejected by the server if the (possibly overridden) risk_level is R2/R3.",
)
def review_task(task_id: int, request: TaskReviewRequest, db: Session = Depends(get_db)):
    return TaskService(db).review_task(
        task_id,
        request.reviewer_id,
        request.decision,
        request.approved_complexity,
        request.approved_risk,
        request.approved_evidence_level,
        request.comment,
    )

@router.get("/{task_id}/reviews", response_model=List[TaskReviewRead], summary="List the review history for a task")
def list_task_reviews(task_id: int, db: Session = Depends(get_db)):
    return TaskService(db).list_task_reviews(task_id)

@router.post(
    "/{task_id}/join",
    response_model=TaskSubmissionRead,
    summary="A student joins a task, starting its submission workflow",
)
def join_task(task_id: int, request: JoinTaskRequest, db: Session = Depends(get_db)):
    return TaskService(db).join_task(task_id, request.student_id)

@router.get(
    "/{task_id}/progress",
    response_model=TaskProgressRead,
    summary="A student's progress on a task, rolled up across sub-tasks if any",
)
def get_task_progress(task_id: int, student_id: int, db: Session = Depends(get_db)):
    return TaskService(db).get_task_progress(task_id, student_id)

@router.post(
    "/{task_id}/submit",
    response_model=TaskSubmissionRead,
    summary="Student submits their report/link for a task they've joined",
    description="Scoped by task_id + student_id (in the body), not submission_id — "
                "the student only knows which task they joined.",
)
def submit_report(task_id: int, request: SubmitReportRequest, db: Session = Depends(get_db)):
    reflection = request.student_reflection.model_dump() if request.student_reflection else None
    return TaskService(db).submit_report(task_id, request.student_id, request.report_url, reflection)

@router.post(
    "/submissions/{submission_id}/files",
    response_model=TaskSubmissionFileRead,
    summary="Register metadata for one uploaded deliverable file",
    description="The binary itself is uploaded through the caller's own storage pipeline; this only records what "
                "was uploaded. Max 10 files/submission (requirements.md §14); size_bytes is capped at 50MB/file.",
)
def register_submission_file(submission_id: int, request: RegisterSubmissionFileRequest, db: Session = Depends(get_db)):
    return TaskService(db).register_submission_file(submission_id, request.model_dump())

@router.post(
    "/submissions/{submission_id}/files/upload",
    response_model=TaskSubmissionFileRead,
    summary="Upload a deliverable file directly",
    description="Stores the file in GCS and registers it in one step — the resulting file_url is public (anyone "
                "with the link can view it, no auth required; a deliberate MVP/demo simplification via a bucket-level "
                "IAM exception, see docs/DATA_MODEL.md). Same 10 files/submission limit as the metadata-only "
                "registration endpoint above.",
)
async def upload_submission_file(submission_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    return TaskService(db).upload_submission_file(submission_id, file.filename, file.content_type, content)

@router.get("/submissions/{submission_id}/files", response_model=List[TaskSubmissionFileRead], summary="List a submission's uploaded files")
def list_submission_files(submission_id: int, db: Session = Depends(get_db)):
    return TaskService(db).list_submission_files(submission_id)

@router.post("/submissions/{submission_id}/auto-check", response_model=TaskSubmissionRead, summary="Run the automated format/completeness check")
def run_auto_check(
    submission_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    submission = TaskService(db).run_auto_check(submission_id)
    _schedule_career_refresh(background_tasks, submission)
    return submission

@router.post("/submissions/{submission_id}/mentor-review", response_model=TaskSubmissionRead, summary="Mentor approves or rejects the submission")
def mentor_review(
    submission_id: int,
    request: MentorReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    submission = TaskService(db).mentor_review(submission_id, request.approved, request.feedback)
    _schedule_career_refresh(background_tasks, submission)
    return submission

@router.post(
    "/submissions/{submission_id}/scores",
    response_model=TaskSubmissionScoreRead,
    summary="Record (or update) the score for one evaluation criterion",
    description="Upsert semantics: re-scoring the same criterion_id for this submission updates the existing score rather than duplicating it.",
)
def score_criterion(submission_id: int, request: ScoreCriterionRequest, db: Session = Depends(get_db)):
    return TaskService(db).score_criterion(submission_id, request.criterion_id, request.score_percent, request.feedback, request.scored_by)

@router.get("/submissions/{submission_id}/scores", response_model=List[TaskSubmissionScoreRead], summary="List per-criterion scores for a submission")
def list_scores(submission_id: int, db: Session = Depends(get_db)):
    return TaskService(db).get_scores(submission_id)

@router.post(
    "/submissions/{submission_id}/complete",
    response_model=TaskSubmissionRead,
    summary="AI or mentor finalizes the submission and records competency points",
    description="Only valid once the required prior gate (auto-check and/or mentor approval, per the task's config) has passed.",
)
def complete_submission(
    submission_id: int,
    request: CompleteSubmissionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    submission = TaskService(db).complete_submission(submission_id, request.completed_by)
    _schedule_career_refresh(background_tasks, submission)
    return submission

@router.get("/submissions/{submission_id}", response_model=TaskSubmissionRead, summary="Get a submission's detail")
def get_submission(submission_id: int, db: Session = Depends(get_db)):
    return TaskService(db).get_submission(submission_id)

@router.post(
    "/seed-demo-data",
    tags=["Dev Tools"],
    summary="Populate a sample company + task with 2 sub-tasks for local testing/demos",
    description="Idempotent (matched by company slug / task title). Disabled when ENABLE_SEED_ENDPOINT=false, "
                "which should be the case in any production deployment.",
)
def seed_demo_data(db: Session = Depends(get_db)):
    if not settings.ENABLE_SEED_ENDPOINT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Data seeding is disabled in this environment")
    return TaskService(db).seed_demo_data()
