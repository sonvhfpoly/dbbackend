from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    TaskDifficulty,
)
from .service import TaskService

router = APIRouter(prefix="/tasks", tags=["Task Marketplace"])

@router.post("/companies/", response_model=CompanyRead, summary="Register a company sponsoring tasks")
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    return TaskService(db).create_company(company)

@router.get("/companies/", response_model=List[CompanyRead], summary="List companies")
def list_companies(db: Session = Depends(get_db)):
    return TaskService(db).list_companies()

@router.post("/", response_model=TaskRead, summary="Create a task (or a sub-task, via parent_task_id)")
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    return TaskService(db).create_task(task)

@router.get("/", response_model=List[TaskRead], summary="List root tasks, optionally filtered")
def list_tasks(
    difficulty: Optional[TaskDifficulty] = None,
    company_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return TaskService(db).list_tasks(difficulty=difficulty.value if difficulty else None, company_id=company_id)

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
@router.get("/{task_id}", response_model=TaskRead, summary="Get a task's detail, including its sub-tasks")
def get_task(task_id: int, db: Session = Depends(get_db)):
    return TaskService(db).get_task(task_id)

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
    return TaskService(db).submit_report(task_id, request.student_id, request.report_url)

@router.post("/submissions/{submission_id}/auto-check", response_model=TaskSubmissionRead, summary="Run the automated format/completeness check")
def run_auto_check(submission_id: int, db: Session = Depends(get_db)):
    return TaskService(db).run_auto_check(submission_id)

@router.post("/submissions/{submission_id}/mentor-review", response_model=TaskSubmissionRead, summary="Mentor approves or rejects the submission")
def mentor_review(submission_id: int, request: MentorReviewRequest, db: Session = Depends(get_db)):
    return TaskService(db).mentor_review(submission_id, request.approved, request.feedback)

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
def complete_submission(submission_id: int, request: CompleteSubmissionRequest, db: Session = Depends(get_db)):
    return TaskService(db).complete_submission(submission_id, request.completed_by)

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
