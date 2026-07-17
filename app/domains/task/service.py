import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.chatbot.service import ChatbotService
from .repository import TaskRepository
from .models import SubmissionStatus, CompletionActor, TaskDifficulty, Task
from .schemas import CompanyCreate, TaskCreate
from .seed_data import SEED_COMPANY, SEED_ROOT_TASK, SEED_SUB_TASKS

# Distinct from the chatbot domain's conversational persona and the guidance
# domain's recommendation prompt: this one asks the model to act as a task
# designer, judging difficulty and whether a task is broad enough to warrant
# splitting into sub-tasks.
TASK_PLANNING_SYSTEM_PROMPT = (
    "You are a task-design assistant for a student career-guidance platform. "
    "Given a company-sponsored practical task (title, context, scope, estimated hours), "
    "assess its difficulty and decide whether it should be broken down into sub-tasks "
    "so students can complete it incrementally and earn points progressively. "
    "Only propose a split when the task is genuinely too broad for one submission "
    "(e.g. it spans multiple distinct deliverables, or its estimated hours are much "
    "longer than a single focused session) — small or already well-scoped tasks must NOT "
    "be split. Respond with ONLY a JSON object, no prose, no markdown code fences, in "
    "exactly this shape: {\"difficulty\": \"EASY\"|\"MEDIUM\"|\"HARD\", "
    "\"should_split\": true|false, \"sub_tasks\": [{\"title\": str, \"context\": str, "
    "\"estimated_hours_min\": int, \"estimated_hours_max\": int, \"competency_points\": int, "
    "\"difficulty\": \"EASY\"|\"MEDIUM\"|\"HARD\"}]}. sub_tasks must be [] when should_split "
    "is false. Keep the same language (Vietnamese or English) as the input task."
)

# Used for sub-tasks (and as a fallback for root tasks if ever needed): a
# narrower prompt than TASK_PLANNING_SYSTEM_PROMPT since sub-tasks aren't
# themselves candidates for further splitting.
DIFFICULTY_ASSESSMENT_SYSTEM_PROMPT = (
    "You assess the difficulty of a practical task for a student career-guidance platform. "
    "Given a task's title, context, scope, and estimated hours, classify its difficulty. "
    "Respond with ONLY a JSON object, no prose, no markdown code fences, in exactly this "
    "shape: {\"difficulty\": \"EASY\"|\"MEDIUM\"|\"HARD\"}."
)

# Used to satisfy the NOT NULL difficulty column while an AI assessment is
# pending/unavailable — overwritten as soon as the assessment succeeds.
DEFAULT_DIFFICULTY = TaskDifficulty.MEDIUM

class TaskService:
    def __init__(self, db: Session):
        self.repo = TaskRepository(db)
        self.chatbot = ChatbotService()

    # ---- Company ----

    def create_company(self, company: CompanyCreate):
        return self.repo.get_or_create_company(company.model_dump())

    def list_companies(self):
        return self.repo.list_companies()

    # ---- Task ----

    def create_task(self, task: TaskCreate):
        data = task.model_dump()
        self._validate_parent(data.get("parent_task_id"))
        self._validate_criteria_weights(data.get("criteria", []))

        is_root = data.get("parent_task_id") is None
        difficulty_unset = data.get("difficulty") is None

        if difficulty_unset and not is_root:
            # Sub-tasks don't go through _ai_plan_subtasks (see below), so if the
            # caller omitted difficulty here it needs its own AI assessment.
            data["difficulty"] = self._ai_assess_difficulty(data) or DEFAULT_DIFFICULTY
        elif difficulty_unset:
            # Root task: placeholder to satisfy the NOT NULL column — the AI
            # planning call below assesses the real difficulty and overwrites it.
            data["difficulty"] = DEFAULT_DIFFICULTY

        created = self.repo.create_task(data)

        # Only for root tasks: a sub-task is already the AI-planned (or manual)
        # granular unit, so it isn't itself a candidate for further splitting
        # (nesting is capped at 2 levels anyway).
        if is_root:
            self._ai_plan_subtasks(created, override_difficulty=difficulty_unset)
            created = self.repo.get_task(created.id)

        return created

    def get_task(self, task_id: int):
        task = self.repo.get_task(task_id)
        if task is None:
            raise EntityNotFoundException("Task", task_id)
        return task

    def list_tasks(self, difficulty: Optional[str] = None, company_id: Optional[int] = None, root_only: bool = True):
        return self.repo.list_tasks(difficulty=difficulty, company_id=company_id, root_only=root_only)

    def _validate_parent(self, parent_task_id: Optional[int]) -> None:
        if parent_task_id is None:
            return
        parent = self.repo.get_task(parent_task_id)
        if parent is None:
            raise EntityNotFoundException("Task", parent_task_id)
        if parent.parent_task_id is not None:
            raise BusinessLogicException(
                f"Task {parent_task_id} is already a sub-task; nesting is limited to 2 levels (Task -> Sub-task)"
            )

    def _validate_criteria_weights(self, criteria: List[dict]) -> None:
        if not criteria:
            return
        total = sum(c["weight_percent"] for c in criteria)
        if total != 100:
            raise BusinessLogicException(f"Evaluation criteria weights must sum to 100, got {total}")

    def _ai_plan_subtasks(self, task: Task, override_difficulty: bool = True) -> None:
        """Best-effort: ask the chatbot to assess difficulty and, if the task is
        genuinely too broad for one submission, split it into sub-tasks. Any
        failure (chatbot unreachable, unparseable reply) is swallowed — AI
        planning is an enhancement on top of task creation, not a requirement
        for it to succeed. override_difficulty=False means the caller already
        gave an explicit difficulty, which the AI's opinion must not clobber."""
        try:
            raw_reply = self.chatbot.complete([
                {"role": "system", "content": TASK_PLANNING_SYSTEM_PROMPT},
                {"role": "user", "content": self._build_planning_prompt(task)},
            ])
            plan = self._parse_planning_output(raw_reply)
        except Exception:
            return

        if override_difficulty:
            difficulty = self._coerce_difficulty(plan.get("difficulty"), fallback=None)
            if difficulty is not None:
                self.repo.update_task(task.id, difficulty=difficulty)

        sub_tasks = plan.get("sub_tasks")
        if not plan.get("should_split") or not isinstance(sub_tasks, list) or not sub_tasks:
            return

        for index, sub in enumerate(sub_tasks):
            if not isinstance(sub, dict) or not sub.get("title"):
                continue
            hours_min = sub.get("estimated_hours_min") or 1
            self.repo.create_task({
                "title": sub["title"],
                "difficulty": self._coerce_difficulty(sub.get("difficulty"), fallback=task.difficulty),
                "company_id": task.company_id,
                "parent_task_id": task.id,
                "sort_order": index,
                "estimated_hours_min": hours_min,
                "estimated_hours_max": sub.get("estimated_hours_max") or hours_min,
                "competency_points": sub.get("competency_points") or 10,
                "context": sub.get("context") or task.context,
                "scope_included": [],
                "scope_excluded": [],
                "requires_auto_check": False,
                "requires_mentor_approval": True,
                "mentor_approval_sla_hours": None,
                "data_privacy_notice": None,
                "inputs": [],
                "outputs": [],
                "criteria": [],
            })

        # Points now roll up from the sub-tasks' own completed submissions
        # (see get_task_progress) — the parent's own static value is stale.
        self.repo.update_task(task.id, competency_points=None)

    def _ai_assess_difficulty(self, data: dict) -> Optional[TaskDifficulty]:
        """Best-effort difficulty-only assessment for tasks that don't go
        through _ai_plan_subtasks (i.e. sub-tasks). Returns None on any
        failure so the caller can fall back to a default."""
        try:
            raw_reply = self.chatbot.complete([
                {"role": "system", "content": DIFFICULTY_ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": self._build_difficulty_prompt(data)},
            ])
            plan = self._parse_planning_output(raw_reply)
        except Exception:
            return None
        return self._coerce_difficulty(plan.get("difficulty"), fallback=None)

    @staticmethod
    def _build_difficulty_prompt(data: dict) -> str:
        return (
            f"Task title: {data.get('title')}\n"
            f"Estimated hours: {data.get('estimated_hours_min')}-{data.get('estimated_hours_max')}\n"
            f"Context: {data.get('context')}\n"
            f"Scope included: {data.get('scope_included') or []}\n"
            f"Scope excluded: {data.get('scope_excluded') or []}\n"
        )

    @staticmethod
    def _build_planning_prompt(task: Task) -> str:
        return (
            f"Task title: {task.title}\n"
            f"Current difficulty: {task.difficulty.value}\n"
            f"Estimated hours: {task.estimated_hours_min}-{task.estimated_hours_max}\n"
            f"Context: {task.context}\n"
            f"Scope included: {task.scope_included or []}\n"
            f"Scope excluded: {task.scope_excluded or []}\n"
        )

    @staticmethod
    def _parse_planning_output(raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            # Strip a markdown code fence some models wrap JSON in despite
            # being told not to.
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("AI planning response was not a JSON object")
        return data

    @staticmethod
    def _coerce_difficulty(value, fallback: Optional[TaskDifficulty]) -> Optional[TaskDifficulty]:
        if isinstance(value, str):
            try:
                return TaskDifficulty(value)
            except ValueError:
                pass
        return fallback

    # ---- Submission workflow ----
    # State machine: JOINED -> SUBMITTED -> AUTO_CHECK_PASSED|AUTO_CHECK_FAILED
    #                       -> MENTOR_APPROVED|MENTOR_REJECTED -> COMPLETED
    # AUTO_CHECK_FAILED/MENTOR_REJECTED both loop back to allow a fresh SUBMITTED.

    def join_task(self, task_id: int, student_id: int):
        self.get_task(task_id)  # 404s if missing
        # Idempotent: re-joining returns the existing submission instead of
        # creating a second, disconnected row for the same (task, student) —
        # otherwise get_latest_submission's ordering would silently orphan
        # whatever progress the first submission already made.
        existing = self.repo.get_latest_submission(task_id, student_id)
        if existing is not None:
            return existing
        return self.repo.create_submission(task_id, student_id)

    def _get_submission_or_404(self, submission_id: int):
        submission = self.repo.get_submission(submission_id)
        if submission is None:
            raise EntityNotFoundException("TaskSubmission", submission_id)
        return submission

    def _require_status(self, submission, allowed: set) -> None:
        if submission.status not in allowed:
            allowed_names = ", ".join(s.value for s in allowed)
            raise BusinessLogicException(
                f"Submission {submission.id} is '{submission.status.value}', expected one of: {allowed_names}"
            )

    def submit_report(self, task_id: int, student_id: int, report_url: str):
        # Scoped by (task_id, student_id): a student only knows which task they
        # joined, not the internal submission_id generated by join_task.
        submission = self.repo.get_latest_submission(task_id, student_id)
        if submission is None:
            raise EntityNotFoundException("TaskSubmission", f"task_id={task_id}, student_id={student_id}")
        self._require_status(submission, {SubmissionStatus.JOINED, SubmissionStatus.AUTO_CHECK_FAILED, SubmissionStatus.MENTOR_REJECTED})
        return self.repo.update_submission(
            submission.id,
            report_url=report_url,
            submitted_at=datetime.utcnow(),
            status=SubmissionStatus.SUBMITTED,
        )

    def run_auto_check(self, submission_id: int):
        """Placeholder check for MVP: a real implementation would inspect the
        submitted file/report (format, size, required sections). Here we only
        verify a report_url was actually provided — the point is to exercise
        the state transition, not to fully specify unstated grading logic."""
        submission = self._get_submission_or_404(submission_id)
        self._require_status(submission, {SubmissionStatus.SUBMITTED})

        passed = bool(submission.report_url)
        result = {"passed": passed, "reason": "report_url present" if passed else "report_url missing"}
        return self.repo.update_submission(
            submission_id,
            auto_check_result=result,
            status=SubmissionStatus.AUTO_CHECK_PASSED if passed else SubmissionStatus.AUTO_CHECK_FAILED,
        )

    def mentor_review(self, submission_id: int, approved: bool, feedback: Optional[str]):
        submission = self._get_submission_or_404(submission_id)
        task = self.get_task(submission.task_id)
        expected = {SubmissionStatus.AUTO_CHECK_PASSED} if task.requires_auto_check else {SubmissionStatus.SUBMITTED}
        self._require_status(submission, expected)
        return self.repo.update_submission(
            submission_id,
            mentor_feedback=feedback,
            mentor_decision_at=datetime.utcnow(),
            status=SubmissionStatus.MENTOR_APPROVED if approved else SubmissionStatus.MENTOR_REJECTED,
        )

    def score_criterion(self, submission_id: int, criterion_id: int, score_percent: int, feedback: Optional[str], scored_by: CompletionActor):
        submission = self._get_submission_or_404(submission_id)
        task = self.get_task(submission.task_id)
        if criterion_id not in {c.id for c in task.criteria}:
            raise BusinessLogicException(f"Criterion {criterion_id} does not belong to task {task.id}")
        return self.repo.upsert_score(submission_id, criterion_id, score_percent, feedback, scored_by)

    def get_scores(self, submission_id: int):
        self._get_submission_or_404(submission_id)
        return self.repo.get_scores_for_submission(submission_id)

    def complete_submission(self, submission_id: int, completed_by: CompletionActor):
        submission = self._get_submission_or_404(submission_id)
        task = self.get_task(submission.task_id)

        if task.requires_mentor_approval:
            expected = {SubmissionStatus.MENTOR_APPROVED}
        elif task.requires_auto_check:
            expected = {SubmissionStatus.AUTO_CHECK_PASSED}
        else:
            expected = {SubmissionStatus.SUBMITTED}
        self._require_status(submission, expected)

        return self.repo.update_submission(
            submission_id,
            status=SubmissionStatus.COMPLETED,
            completed_by=completed_by,
            points_awarded=task.competency_points,
            completed_at=datetime.utcnow(),
        )

    def get_submission(self, submission_id: int):
        return self._get_submission_or_404(submission_id)

    def list_submissions(self, task_id: Optional[int] = None, student_id: Optional[int] = None):
        return self.repo.list_submissions(task_id=task_id, student_id=student_id)

    # ---- Progress rollup ----

    def get_task_progress(self, task_id: int, student_id: int) -> dict:
        task = self.get_task(task_id)
        sub_tasks = self.repo.get_sub_tasks(task_id)

        if sub_tasks:
            sub_task_progress = []
            total_points = 0
            all_completed = True
            for sub_task in sub_tasks:
                submission = self.repo.get_latest_submission(sub_task.id, student_id)
                is_done = submission is not None and submission.status == SubmissionStatus.COMPLETED
                if not is_done:
                    all_completed = False
                if is_done and submission.points_awarded:
                    total_points += submission.points_awarded
                sub_task_progress.append({
                    "task_id": sub_task.id,
                    "title": sub_task.title,
                    "status": submission.status if submission else None,
                    "points_awarded": submission.points_awarded if submission else None,
                })
            return {
                "task_id": task_id,
                "student_id": student_id,
                "is_fully_completed": all_completed,
                "total_points_awarded": total_points,
                "sub_tasks": sub_task_progress,
                "submission": None,
            }

        submission = self.repo.get_latest_submission(task_id, student_id)
        return {
            "task_id": task_id,
            "student_id": student_id,
            "is_fully_completed": submission is not None and submission.status == SubmissionStatus.COMPLETED,
            "total_points_awarded": submission.points_awarded if submission else None,
            "sub_tasks": [],
            "submission": submission,
        }

    # ---- Seed ----

    def seed_demo_data(self):
        company = self.repo.get_or_create_company(dict(SEED_COMPANY))

        root_task = self.repo.get_task_by_title(SEED_ROOT_TASK["title"])
        root_created = False
        if root_task is None:
            root_data = dict(SEED_ROOT_TASK)
            root_data["company_id"] = company.id
            root_task = self.repo.create_task(root_data)
            root_created = True

        sub_tasks_created = 0
        for sub in SEED_SUB_TASKS:
            existing = self.repo.get_task_by_title(sub["title"])
            if existing is None:
                sub_data = dict(sub)
                sub_data["company_id"] = company.id
                sub_data["parent_task_id"] = root_task.id
                self.repo.create_task(sub_data)
                sub_tasks_created += 1

        return {
            "company_id": company.id,
            "root_task_id": root_task.id,
            "root_task_created": root_created,
            "sub_tasks_created": sub_tasks_created,
        }
