import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import status
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.chatbot.service import ChatbotService
from . import storage
from .repository import TaskRepository
from .models import SubmissionStatus, CompletionActor, Task, TaskReviewStatus, TaskRiskLevel, TaskComplexity
from .schemas import CompanyCreate, TaskCreate

# R2/R3 tasks can never be approved in MVP (no Expert Reviewer exists to
# review them) — see requirements.md section 4.2.
_BLOCKED_APPROVAL_RISK_LEVELS = {TaskRiskLevel.R2, TaskRiskLevel.R3}
from .seed_data import SEED_COMPANY, SEED_ROOT_TASK, SEED_SUB_TASKS

# Distinct from the chatbot domain's conversational persona and the guidance
# domain's recommendation prompt: this one asks the model to act as a task
# designer, judging T-level complexity and whether a task is broad enough to
# warrant splitting into sub-tasks.
TASK_PLANNING_SYSTEM_PROMPT = (
    "You are a task-design assistant for a student career-guidance platform. "
    "Given a company-sponsored practical task (title, context, scope, estimated hours), "
    "assess its complexity level and decide whether it should be broken down into sub-tasks "
    "so students can complete it incrementally and earn points progressively. "
    "Only propose a split when the task is genuinely too broad for one submission "
    "(e.g. it spans multiple distinct deliverables, or its estimated hours are much "
    "longer than a single focused session) — small or already well-scoped tasks must NOT "
    "be split. Respond with ONLY a JSON object, no prose, no markdown code fences, in "
    "exactly this shape: {\"complexity_level\": \"T1\"|\"T2\"|\"T3\", "
    "\"should_split\": true|false, \"sub_tasks\": [{\"title\": str, \"context\": str, "
    "\"estimated_hours_min\": int, \"estimated_hours_max\": int, \"competency_points\": int, "
    "\"complexity_level\": \"T1\"|\"T2\"|\"T3\"}]}. sub_tasks must be [] when should_split "
    "is false. Keep the same language (Vietnamese or English) as the input task."
)

# Used for sub-tasks (and as a fallback for root tasks if ever needed): a
# narrower prompt than TASK_PLANNING_SYSTEM_PROMPT since sub-tasks aren't
# themselves candidates for further splitting.
COMPLEXITY_ASSESSMENT_SYSTEM_PROMPT = (
    "You assess the complexity level (T-level) of a practical task for a student career-guidance "
    "platform. Given a task's title, context, scope, and estimated hours, classify it as T1 "
    "(micro-task, clear brief), T2 (task with guidance/checkpoints), or T3 (requires a mentor "
    "capable of reviewing it). Respond with ONLY a JSON object, no prose, no markdown code "
    "fences, in exactly this shape: {\"complexity_level\": \"T1\"|\"T2\"|\"T3\"}."
)

# Used to satisfy the NOT NULL complexity_level column while an AI assessment
# is pending/unavailable — overwritten as soon as the assessment succeeds.
DEFAULT_COMPLEXITY = TaskComplexity.T1

# Lazily created (see TaskService.resolve_company_id) the first time a task
# is created with a missing or unregistered company_id, so task creation
# never hard-fails on a bad FK — matched by slug, same idempotent pattern as
# get_or_create_company's other callers.
PLACEHOLDER_COMPANY = {
    "name": "Unregistered Company",
    "slug": "unregistered-company",
    "description": "Auto-created placeholder used when a task references a company_id that isn't registered.",
}

class TaskService:
    def __init__(self, db: Session):
        self.repo = TaskRepository(db)
        self.chatbot = ChatbotService()

    # ---- Company ----

    def create_company(self, company: CompanyCreate):
        return self.repo.get_or_create_company(company.model_dump())

    def list_companies(self):
        return self.repo.list_companies()

    def resolve_company_id(self, company_id: Optional[int]) -> int:
        """Returns company_id as-is if it references a real Company; otherwise
        falls back to a shared placeholder company (auto-created on first use).
        Called from both create_task below and TaskBuilderService.start_conversation
        so task creation never hard-fails on a missing/stale company_id — the
        FK stays NOT NULL at the DB level, every row just always gets a real one."""
        if company_id is not None:
            company = self.repo.get_company(company_id)
            if company is not None:
                return company.id
        return self.repo.get_or_create_company(dict(PLACEHOLDER_COMPANY)).id

    # ---- Task ----

    def create_task(self, task: TaskCreate):
        data = task.model_dump()
        skip_ai_planning = data.pop("skip_ai_planning", False)
        data["company_id"] = self.resolve_company_id(data.get("company_id"))
        self._validate_parent(data.get("parent_task_id"))
        self._validate_criteria_weights(data.get("criteria", []))

        is_root = data.get("parent_task_id") is None
        complexity_unset = data.get("complexity_level") is None

        if complexity_unset and not is_root:
            # Sub-tasks don't go through _ai_plan_subtasks (see below), so if the
            # caller omitted complexity_level here it needs its own AI assessment
            # (unless skipped — then it just falls back to the default below).
            data["complexity_level"] = (
                None if skip_ai_planning else self._ai_assess_complexity(data)
            ) or DEFAULT_COMPLEXITY
        elif complexity_unset:
            # Root task: placeholder to satisfy the NOT NULL column — the AI
            # planning call below assesses the real complexity_level and overwrites it
            # (unless skipped, in which case this default is the final value).
            data["complexity_level"] = DEFAULT_COMPLEXITY

        try:
            created = self.repo.create_task(data)
        except ValueError as exc:
            self.repo.db.rollback()
            raise BusinessLogicException(str(exc)) from exc
        except IntegrityError as exc:
            # Safety net, not the primary fix: company_id is already resolved
            # to a real row above, so this should be rare in practice — but no
            # constraint violation anywhere in this path should ever leak out
            # as a raw 500 the way the original company_id bug did.
            self.repo.db.rollback()
            raise BusinessLogicException(f"Could not create task: {exc.orig}") from exc

        # Only for root tasks: a sub-task is already the AI-planned (or manual)
        # granular unit, so it isn't itself a candidate for further splitting
        # (nesting is capped at 2 levels anyway).
        if is_root:
            self._ai_plan_subtasks(created, override_complexity=complexity_unset, skip=skip_ai_planning)
            created = self.repo.get_task(created.id)

        return created

    def get_task(self, task_id: int):
        task = self.repo.get_task(task_id)
        if task is None:
            raise EntityNotFoundException("Task", task_id)
        return task

    def set_task_skills(self, task_id: int, skill_ids: List[int]):
        task = self.get_task(task_id)
        try:
            return self.repo.set_task_skills(task, list(dict.fromkeys(skill_ids)))
        except ValueError as exc:
            raise BusinessLogicException(str(exc)) from exc

    def delete_task(self, task_id: int, force: bool = False) -> None:
        """Deletes a task. Evidence claims against it (or any of its
        sub-tasks) always block deletion outright — evidence has already
        updated a StudentSkillProfile elsewhere (see evidence/service.py's
        mentor_decide), and this method has no way to safely unwind that, so
        it never cascades into evidence regardless of force. Sub-tasks and
        their submissions/reviews only block when force=False; force=True
        deletes them (child-before-parent, to satisfy the parent_task_id FK)
        along with this task."""
        task = self.get_task(task_id)  # 404s if missing
        sub_tasks = self.repo.get_sub_tasks(task_id)
        all_ids = [task_id] + [sub.id for sub in sub_tasks]

        evidence_count = sum(self.repo.count_evidence_claims_for_task(tid) for tid in all_ids)
        if evidence_count:
            raise BusinessLogicException(
                f"Task {task_id} (or its sub-tasks) has {evidence_count} evidence claim(s) recorded "
                "against it — deleting a task never cascades into evidence records."
            )

        submission_count = sum(self.repo.count_submissions_for_task(tid) for tid in all_ids)
        if (sub_tasks or submission_count) and not force:
            raise BusinessLogicException(
                f"Task {task_id} has {len(sub_tasks)} sub-task(s) and {submission_count} submission(s); "
                "pass force=true to delete them along with the task, or remove them first."
            )

        for sub_task in sub_tasks:
            self.repo.delete_submissions_for_task(sub_task.id)
            self.repo.delete_task_row(sub_task)
        self.repo.delete_submissions_for_task(task_id)
        self.repo.delete_task_row(task)

    def list_tasks(
        self,
        complexity_level: Optional[str] = None,
        company_id: Optional[int] = None,
        root_only: bool = True,
        review_status: Optional[str] = None,
    ):
        return self.repo.list_tasks(complexity_level=complexity_level, company_id=company_id, root_only=root_only, review_status=review_status)

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

    # ---- Task review (mentor approves/rejects the Task itself) ----

    def review_task(
        self,
        task_id: int,
        reviewer_id: int,
        decision: TaskReviewStatus,
        approved_complexity: Optional[str],
        approved_risk: Optional[str],
        approved_evidence_level: Optional[str],
        comment: Optional[str],
    ):
        task = self.get_task(task_id)
        if decision == TaskReviewStatus.PENDING_MENTOR_APPROVAL:
            raise BusinessLogicException("decision must be APPROVED, REJECTED, or NEED_MORE_INFO")
        if task.review_status not in {TaskReviewStatus.PENDING_MENTOR_APPROVAL, TaskReviewStatus.NEED_MORE_INFO}:
            raise BusinessLogicException(
                f"Task {task_id} review_status is '{task.review_status.value}'; only tasks pending approval or needing more info can be reviewed"
            )

        effective_risk = TaskRiskLevel(approved_risk) if approved_risk else task.risk_level
        if decision == TaskReviewStatus.APPROVED and effective_risk in _BLOCKED_APPROVAL_RISK_LEVELS:
            raise BusinessLogicException(
                f"Task {task_id} has risk_level {effective_risk.value}; tasks at R2/R3 cannot be approved in MVP (no Expert Reviewer)"
            )

        review = self.repo.create_task_review(task_id, {
            "reviewer_id": reviewer_id,
            "decision": decision,
            "approved_complexity": approved_complexity,
            "approved_risk": approved_risk,
            "approved_evidence_level": approved_evidence_level,
            "comment": comment,
        })

        update_fields = {"review_status": decision}
        if approved_complexity:
            update_fields["complexity_level"] = approved_complexity
        if approved_risk:
            update_fields["risk_level"] = approved_risk
        if approved_evidence_level:
            update_fields["target_evidence_level"] = approved_evidence_level
        self.repo.update_task(task_id, **update_fields)

        # Sub-tasks never appear in list_pending_approval_tasks (root_only=True)
        # and have no review UI of their own, so a mentor only ever reviews the
        # root. Without this, sub-tasks stay stuck at PENDING_MENTOR_APPROVAL
        # forever and join_task (which gates per-task) permanently locks them out.
        if task.parent_task_id is None:
            self._propagate_review_to_subtasks(task_id, decision)

        return review

    def _propagate_review_to_subtasks(self, parent_task_id: int, decision: TaskReviewStatus) -> None:
        for sub_task in self.repo.get_sub_tasks(parent_task_id):
            if decision == TaskReviewStatus.APPROVED and sub_task.risk_level in _BLOCKED_APPROVAL_RISK_LEVELS:
                # Same R2/R3 MVP gate as the root check above, evaluated against
                # the sub-task's own risk_level — leave it un-approved rather
                # than silently letting it through via the parent's decision.
                continue
            self.repo.update_task(sub_task.id, review_status=decision)

    def list_task_reviews(self, task_id: int):
        self.get_task(task_id)  # 404s if missing
        return self.repo.list_task_reviews(task_id)

    def _ai_plan_subtasks(self, task: Task, override_complexity: bool = True, skip: bool = False) -> None:
        """Best-effort: ask the chatbot to assess T-level complexity and, if the
        task is genuinely too broad for one submission, split it into sub-tasks.
        Any failure (chatbot unreachable, unparseable reply) is swallowed — AI
        planning is an enhancement on top of task creation, not a requirement
        for it to succeed. override_complexity=False means the caller already
        gave an explicit complexity_level, which the AI's opinion must not
        clobber. skip=True bypasses the AI call entirely (see TaskCreate.skip_ai_planning) —
        useful for demos/tests that want a single flat task without an LLM round-trip."""
        if skip:
            return
        try:
            raw_reply = self.chatbot.complete([
                {"role": "system", "content": TASK_PLANNING_SYSTEM_PROMPT},
                {"role": "user", "content": self._build_planning_prompt(task)},
            ], json_mode=True)
            plan = self._parse_planning_output(raw_reply)
        except Exception:
            return

        if override_complexity:
            complexity = self._coerce_complexity(plan.get("complexity_level"), fallback=None)
            if complexity is not None:
                self.repo.update_task(task.id, complexity_level=complexity)

        sub_tasks = plan.get("sub_tasks")
        if not plan.get("should_split") or not isinstance(sub_tasks, list) or not sub_tasks:
            return

        for index, sub in enumerate(sub_tasks):
            if not isinstance(sub, dict) or not sub.get("title"):
                continue
            hours_min = sub.get("estimated_hours_min") or 1
            self.repo.create_task({
                "title": sub["title"],
                "complexity_level": self._coerce_complexity(sub.get("complexity_level"), fallback=task.complexity_level),
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
                "checkpoints": [],
                "risk_level": task.risk_level,
                "target_evidence_level": task.target_evidence_level,
                "inputs": [],
                "outputs": [],
                "criteria": [],
                "skill_ids": [skill.id for skill in getattr(task, "skills", [])],
            })

        # Points now roll up from the sub-tasks' own completed submissions
        # (see get_task_progress) — the parent's own static value is stale.
        self.repo.update_task(task.id, competency_points=None)

    def _ai_assess_complexity(self, data: dict) -> Optional[TaskComplexity]:
        """Best-effort complexity-only assessment for tasks that don't go
        through _ai_plan_subtasks (i.e. sub-tasks). Returns None on any
        failure so the caller can fall back to a default."""
        try:
            raw_reply = self.chatbot.complete([
                {"role": "system", "content": COMPLEXITY_ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": self._build_complexity_prompt(data)},
            ], json_mode=True)
            plan = self._parse_planning_output(raw_reply)
        except Exception:
            return None
        return self._coerce_complexity(plan.get("complexity_level"), fallback=None)

    @staticmethod
    def _build_complexity_prompt(data: dict) -> str:
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
            f"Current complexity_level: {task.complexity_level.value}\n"
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
    def _coerce_complexity(value, fallback: Optional[TaskComplexity]) -> Optional[TaskComplexity]:
        if isinstance(value, str):
            try:
                return TaskComplexity(value)
            except ValueError:
                pass
        return fallback

    # ---- Submission workflow ----
    # State machine: JOINED -> SUBMITTED -> AUTO_CHECK_PASSED|AUTO_CHECK_FAILED -> MENTOR_REJECTED|COMPLETED
    # Whichever gate a task actually requires (auto-check and/or mentor
    # approval) is always the LAST step, so passing/approving completes the
    # submission immediately (points_awarded + completed_at) rather than
    # resting at an intermediate "approved but not completed" status that
    # needs a separate call to close out — requirements.md's Mentor
    # functional requirements table has no distinct "close submission" action
    # after "Approve Submission" (MEN-16), and the Student Task Flow (§11)
    # ends at "Mentor Review" with no further explicit step either.
    # AUTO_CHECK_FAILED/MENTOR_REJECTED both loop back to allow a fresh SUBMITTED.

    def join_task(self, task_id: int, student_id: int):
        task = self.get_task(task_id)  # 404s if missing
        if task.review_status != TaskReviewStatus.APPROVED:
            raise BusinessLogicException(
                f"Task {task_id} is not open to students yet (review_status={task.review_status.value})"
            )
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

    def submit_report(self, task_id: int, student_id: int, report_url: str, student_reflection: Optional[dict] = None):
        # Scoped by (task_id, student_id): a student only knows which task they
        # joined, not the internal submission_id generated by join_task.
        submission = self.repo.get_latest_submission(task_id, student_id)
        if submission is None:
            raise EntityNotFoundException("TaskSubmission", f"task_id={task_id}, student_id={student_id}")
        self._require_status(submission, {SubmissionStatus.JOINED, SubmissionStatus.AUTO_CHECK_FAILED, SubmissionStatus.MENTOR_REJECTED})
        submitted_at = datetime.utcnow()
        # requirements.md §12: joined_at doubles as "accepted_at" in this MVP
        # (see TaskSubmission.joined_at) — elapsed time is display-only and
        # must never be treated as a Skill Signal (see TaskSubmissionRead).
        elapsed_seconds = int((submitted_at - submission.joined_at).total_seconds())
        return self.repo.update_submission(
            submission.id,
            report_url=report_url,
            student_reflection=student_reflection,
            submitted_at=submitted_at,
            elapsed_seconds=elapsed_seconds,
            status=SubmissionStatus.SUBMITTED,
            # Clear the previous review cycle's verdict — a resubmission after
            # MENTOR_REJECTED/AUTO_CHECK_FAILED is unreviewed work; leaving the
            # old mentor_feedback/mentor_decision_at/auto_check_result in place
            # would make this new submission look already-decided even though
            # nobody has looked at it yet. No-op on a first-time submit (JOINED
            # -> SUBMITTED), since these are already None at that point.
            mentor_feedback=None,
            mentor_decision_at=None,
            auto_check_result=None,
        )

    # ---- Submission files ----
    # requirements.md §14: max 50MB/file and max 10 files/submission. The
    # 50MB bound is enforced twice: RegisterSubmissionFileRequest's size_bytes
    # field (metadata-only path, caller self-reports the size) and explicitly
    # below in upload_submission_file (real upload path, where we control the
    # actual bytes and can't trust a self-reported size).

    MAX_FILES_PER_SUBMISSION = 10
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

    def register_submission_file(self, submission_id: int, data: dict):
        """For a file already hosted elsewhere (requirements.md §14's "external
        link" case) — the caller supplies file_url directly. For an actual
        upload handled by this backend, see upload_submission_file below."""
        return self._create_submission_file(submission_id, data)

    def upload_submission_file(self, submission_id: int, filename: str, content_type: Optional[str], content: bytes):
        """Uploads the file to GCS (public URL — see domains/task/storage.py)
        and registers it in one step, instead of requiring the caller to
        host it themselves first."""
        self._get_submission_or_404(submission_id)  # 404s before spending an upload on a bad submission_id
        if len(content) > self.MAX_FILE_SIZE_BYTES:
            raise BusinessLogicException(
                f"File exceeds the {self.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB/file limit",
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            )
        file_url = storage.upload_submission_file(submission_id, filename, content_type, content)
        return self._create_submission_file(submission_id, {
            "file_name": filename,
            "mime_type": content_type or "application/octet-stream",
            "size_bytes": len(content),
            "file_url": file_url,
        })

    def _create_submission_file(self, submission_id: int, data: dict):
        self._get_submission_or_404(submission_id)
        if self.repo.count_submission_files(submission_id) >= self.MAX_FILES_PER_SUBMISSION:
            raise BusinessLogicException(
                f"Submission {submission_id} already has the maximum of {self.MAX_FILES_PER_SUBMISSION} files"
            )
        # Placeholder scan, same convention as run_auto_check: no real virus
        # scanner is integrated in this MVP, so registration marks the file
        # PASSED immediately rather than leaving it stuck at PENDING forever.
        return self.repo.create_submission_file(submission_id, {**data, "scan_status": "PASSED"})

    def list_submission_files(self, submission_id: int):
        self._get_submission_or_404(submission_id)
        return self.repo.list_submission_files(submission_id)

    def run_auto_check(self, submission_id: int):
        """Placeholder check for MVP: a real implementation would inspect the
        submitted file/report (format, size, required sections). Here we only
        verify a report_url was actually provided — the point is to exercise
        the state transition, not to fully specify unstated grading logic."""
        submission = self._get_submission_or_404(submission_id)
        self._require_status(submission, {SubmissionStatus.SUBMITTED})
        task = self.get_task(submission.task_id)

        passed = bool(submission.report_url)
        result = {"passed": passed, "reason": "report_url present" if passed else "report_url missing"}

        if passed and not task.requires_mentor_approval:
            # No mentor gate configured for this task — auto-check passing is
            # the terminal step, so complete right away instead of leaving
            # the submission stranded at AUTO_CHECK_PASSED with no mentor
            # ever going to call the separate /complete endpoint on it.
            completed = self.repo.update_submission(
                submission_id, auto_check_result=result, status=SubmissionStatus.COMPLETED,
                completed_by=CompletionActor.AI, points_awarded=task.competency_points,
                completed_at=datetime.utcnow(),
            )
            return completed

        return self.repo.update_submission(
            submission_id,
            auto_check_result=result,
            status=SubmissionStatus.AUTO_CHECK_PASSED if passed else SubmissionStatus.AUTO_CHECK_FAILED,
        )

    def mentor_review(self, submission_id: int, approved: bool, feedback: Optional[str]):
        submission = self._get_submission_or_404(submission_id)
        task = self.get_task(submission.task_id)
        expected = {SubmissionStatus.SUBMITTED}
        if task.requires_auto_check:
            expected.add(SubmissionStatus.AUTO_CHECK_PASSED)
        self._require_status(submission, expected)

        if not approved:
            return self.repo.update_submission(
                submission_id,
                mentor_feedback=feedback,
                mentor_decision_at=datetime.utcnow(),
                status=SubmissionStatus.MENTOR_REJECTED,
            )

        # Mentor approval is always the final gate whenever a mentor is
        # involved at all (requires_mentor_approval=True is why this method
        # is being called) — complete immediately instead of leaving the
        # submission at MENTOR_APPROVED waiting on a separate, easy-to-miss
        # /complete call that a caller may never make (see complete_submission).
        completed = self.repo.update_submission(
            submission_id,
            mentor_feedback=feedback,
            mentor_decision_at=datetime.utcnow(),
            status=SubmissionStatus.COMPLETED,
            completed_by=CompletionActor.MENTOR,
            points_awarded=task.competency_points,
            completed_at=datetime.utcnow(),
        )
        return completed

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
        """mentor_review/run_auto_check now complete a submission automatically
        the moment their configured gate passes (see above) — each is always
        the final step whenever it applies, so this endpoint is only still
        reachable for: (a) a task requiring neither gate at all (completes
        straight from SUBMITTED — the caller has to say who's completing it,
        since nothing evaluated it), or (b) a submission stranded at
        MENTOR_APPROVED from before auto-completion shipped."""
        submission = self._get_submission_or_404(submission_id)
        task = self.get_task(submission.task_id)

        if submission.status == SubmissionStatus.MENTOR_APPROVED:
            expected = {SubmissionStatus.MENTOR_APPROVED}
        elif task.requires_auto_check or task.requires_mentor_approval:
            raise BusinessLogicException(
                f"Submission {submission_id}'s task completes automatically once its configured gate "
                "(auto-check and/or mentor approval) passes — this endpoint doesn't apply here."
            )
        else:
            expected = {SubmissionStatus.SUBMITTED}
        self._require_status(submission, expected)

        completed = self.repo.update_submission(
            submission_id,
            status=SubmissionStatus.COMPLETED,
            completed_by=completed_by,
            points_awarded=task.competency_points,
            completed_at=datetime.utcnow(),
        )
        return completed

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
            # Demo/local data only: real tasks require an explicit mentor
            # review (see review_task) before students can join them.
            root_task = self.repo.update_task(root_task.id, review_status=TaskReviewStatus.APPROVED)
            root_created = True

        sub_tasks_created = 0
        for sub in SEED_SUB_TASKS:
            existing = self.repo.get_task_by_title(sub["title"])
            if existing is None:
                sub_data = dict(sub)
                sub_data["company_id"] = company.id
                sub_data["parent_task_id"] = root_task.id
                created_sub = self.repo.create_task(sub_data)
                self.repo.update_task(created_sub.id, review_status=TaskReviewStatus.APPROVED)
                sub_tasks_created += 1

        return {
            "company_id": company.id,
            "root_task_id": root_task.id,
            "root_task_created": root_created,
            "sub_tasks_created": sub_tasks_created,
        }
