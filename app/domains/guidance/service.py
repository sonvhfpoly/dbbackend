import json
from sqlalchemy.orm import Session
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.student.repository import StudentRepository
from domains.student.models import Student, StudentSkill, StudentSkillProfile
from domains.market.repository import MarketRepository
from domains.chatbot.service import ChatbotService
from domains.task.repository import TaskRepository
from domains.task.models import Task, TaskComplexity, TaskReviewStatus
from .repository import GuidanceRepository
from .models import EducationPath
from .schemas import EducationPathCreate
from .seed_data import SEED_EDUCATION_PATHS
from domains.student.seed_data import SEED_STUDENTS
from typing import List

# Ordered T1->T3 so a match_ratio in [0, 1] can be mapped to a band by index
# (see _complexity_for_match_ratio) instead of a chain of if/elifs.
_COMPLEXITY_BANDS = [TaskComplexity.T1, TaskComplexity.T2, TaskComplexity.T3]

# Used only for the cold-start fallback (see _recommend_via_llm): a brand-new
# student with no skill history yet, or a target Job with no configured skill
# requirements, gives generate_recommendations nothing to compute a match
# from — so we ask the LLM to pick a sensible starter set instead. Distinct
# from the chatbot domain's conversational persona: this asks for a specific,
# machine-parseable output shape rather than a chat reply.
TASK_STARTER_SYSTEM_PROMPT = (
    "You are a task-recommendation engine for a student career-guidance platform. "
    "The student has no measurable skill history yet, or the target job has no "
    "configured skill requirements, so there is nothing to compute a skill match "
    "from. You will be given the student's inferred profile, the title of the job "
    "they're aiming for, and a catalog of currently open tasks (each with a "
    "numeric id, title, complexity level T1-T3, and context). Pick beginner-"
    "friendly tasks STRICTLY from the given catalog (reference them by id — never "
    "invent a task that isn't listed), preferring the lowest complexity (T1) "
    "unless the student's profile suggests they're ready for more. For each pick, "
    "write a reasoning_explanation in Vietnamese connecting the student's profile "
    "and the target job to that specific task. Present every choice as a "
    "reference for the student to weigh, never as a directive. Respond with ONLY "
    "a JSON array, no prose, no markdown code fences, in exactly this shape: "
    "[{\"task_id\": <int>, \"reasoning_explanation\": \"<string>\"}, ...]"
)

class GuidanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GuidanceRepository(db)
        self.student_repo = StudentRepository(db)
        self.market_repo = MarketRepository(db)
        self.task_repo = TaskRepository(db)
        self.chatbot = ChatbotService()

    def create_path(self, path: EducationPathCreate) -> EducationPath:
        return self.repo.create_path(path.model_dump())

    def get_all_paths(self) -> List[EducationPath]:
        return self.repo.get_all_paths()

    def get_recommendations(self, student_id: int):
        # Historical only: generate_recommendations no longer persists (see
        # below), so this will never grow past whatever Recommendation rows
        # were created before that change.
        return self.repo.get_recommendations_by_student(student_id)

    def generate_recommendations(self, student_id: int, target_job_id: int, count: int = 3) -> List[dict]:
        """Recommends the student's next open Task toward a target Job, by
        comparing their known skills (StudentSkill / StudentSkillProfile)
        against the Job's required skill set (JobSkill) — not persisted, so
        callers get a fresh recommendation on every call."""
        student = self.student_repo.get_student(student_id)
        if student is None:
            raise EntityNotFoundException("Student", student_id)

        job = self.market_repo.get_job(target_job_id)
        if job is None:
            raise EntityNotFoundException("Job", target_job_id)

        candidates = self._open_unstarted_leaf_tasks(student_id)
        if not candidates:
            raise BusinessLogicException(
                "No open tasks are available to recommend yet — check back once mentors approve more tasks"
            )

        required_skill_ids = set(self.market_repo.get_job_skill_ids(target_job_id))
        known_skill_ids = self._known_skill_ids(student_id)

        # Cold start: nothing to compute a match from (brand-new student, or a
        # Job with no configured skill requirements) — ask the LLM for a
        # sensible starter set instead of a skill-gap ratio.
        if not required_skill_ids or not known_skill_ids:
            return self._recommend_via_llm(student, job, candidates, count)

        gap_skill_ids = required_skill_ids - known_skill_ids
        matched = len(required_skill_ids) - len(gap_skill_ids)
        match_ratio = round(matched / len(required_skill_ids), 4)
        target_complexity = self._complexity_for_match_ratio(match_ratio)

        pool = [t for t in candidates if t.complexity_level == target_complexity] or candidates
        pool = sorted(pool, key=lambda t: _COMPLEXITY_BANDS.index(t.complexity_level))[:count]

        return [
            self._to_recommendation(
                t,
                f"Bạn đã đáp ứng {matched}/{len(required_skill_ids)} kỹ năng yêu cầu cho "
                f"'{job.title}' ({round(match_ratio * 100)}%). Đây là nhiệm vụ mức "
                f"{t.complexity_level.value}, phù hợp để tiếp tục xây dựng năng lực trước khi "
                "hướng tới công việc này.",
            )
            for t in pool
        ]

    def _open_unstarted_leaf_tasks(self, student_id: int) -> List[Task]:
        """Approved tasks with no sub-tasks of their own (a task with children
        is a container the student completes via those children, not directly
        — see TaskService._ai_plan_subtasks), that this student hasn't already
        joined/submitted."""
        all_tasks = self.task_repo.list_tasks(root_only=False)
        parent_ids = {t.parent_task_id for t in all_tasks if t.parent_task_id is not None}
        open_leaves = [
            t for t in all_tasks
            if t.id not in parent_ids and t.review_status == TaskReviewStatus.APPROVED
        ]
        started_task_ids = {s.task_id for s in self.task_repo.list_submissions(student_id=student_id)}
        return [t for t in open_leaves if t.id not in started_task_ids]

    def _known_skill_ids(self, student_id: int) -> set:
        known = {
            row.skill_id for row in
            self.db.query(StudentSkill.skill_id).filter(StudentSkill.student_id == student_id).all()
        }
        known |= {
            row.skill_id for row in
            self.db.query(StudentSkillProfile.skill_id).filter(StudentSkillProfile.student_id == student_id).all()
        }
        return known

    @staticmethod
    def _complexity_for_match_ratio(match_ratio: float) -> TaskComplexity:
        index = min(int(match_ratio * len(_COMPLEXITY_BANDS)), len(_COMPLEXITY_BANDS) - 1)
        return _COMPLEXITY_BANDS[index]

    @staticmethod
    def _to_recommendation(task: Task, reasoning_explanation: str) -> dict:
        return {
            "task_id": task.id,
            "title": task.title,
            "complexity_level": task.complexity_level,
            "target_evidence_level": task.target_evidence_level,
            "competency_points": task.competency_points,
            "company_id": task.company_id,
            "reasoning_explanation": reasoning_explanation,
        }

    def _recommend_via_llm(self, student: Student, job, candidates: List[Task], count: int) -> List[dict]:
        parsed = []
        try:
            raw_reply = self.chatbot.complete([
                {"role": "system", "content": TASK_STARTER_SYSTEM_PROMPT},
                {"role": "user", "content": self._build_starter_prompt(student, job.title, candidates, count)},
            ])
            parsed = self._parse_llm_output(raw_reply)
        except Exception:
            # Best-effort, same convention as TaskService._ai_plan_subtasks:
            # a cold-start recommendation is an enhancement, not a hard
            # requirement — fall through to the deterministic pick below
            # rather than dead-ending the student with an error.
            pass

        tasks_by_id = {t.id: t for t in candidates}
        picks = []
        for item in parsed:
            task = tasks_by_id.get(item.get("task_id")) if isinstance(item, dict) else None
            reasoning = item.get("reasoning_explanation") if isinstance(item, dict) else None
            if task is not None and isinstance(reasoning, str) and reasoning.strip():
                picks.append((task, reasoning.strip()))

        if not picks:
            ordered = sorted(candidates, key=lambda t: _COMPLEXITY_BANDS.index(t.complexity_level))[:count]
            picks = [
                (t, f"Nhiệm vụ mức {t.complexity_level.value}, phù hợp để bắt đầu hướng tới '{job.title}'.")
                for t in ordered
            ]

        return [self._to_recommendation(t, reasoning) for t, reasoning in picks[:count]]

    @staticmethod
    def _build_starter_prompt(student: Student, job_title: str, candidates: List[Task], count: int) -> str:
        profile = json.dumps(student.ai_inferred_profile or {}, ensure_ascii=False)
        catalog = "\n".join(
            f"- id={t.id}, title={t.title}, complexity={t.complexity_level.value}, context={t.context}"
            for t in candidates
        )
        return (
            f"Student profile (JSON): {profile}\n"
            f"Target job: {job_title}\n\n"
            f"Open tasks:\n{catalog}\n\n"
            f"Recommend {count} tasks from the list above for this student to start with."
        )

    def seed_demo_data(self):
        """Populates a small education-path catalog and a handful of demo
        students (with StudentSkill tags against the shared market skill
        catalog), so the recommendation pipeline — and, downstream, any
        profile/job skill matching — is exercisable end-to-end without
        depending on the student domain's (not yet built) own router."""
        paths_created = 0
        for p in SEED_EDUCATION_PATHS:
            existing = self.db.query(EducationPath).filter(EducationPath.name == p["name"]).first()
            if existing is None:
                self.repo.create_path(dict(p))
                paths_created += 1

        students_created = 0
        demo_student_id = None
        for s in SEED_STUDENTS:
            student = self.student_repo.get_by_email(s["email"])
            if student is None:
                student_data = {k: v for k, v in s.items() if k != "skills"}
                student = self.student_repo.create_student(student_data)
                students_created += 1
            if demo_student_id is None:
                demo_student_id = student.id  # first seed student, kept for backward-compat with callers relying on this key

            for skill_name in s["skills"]:
                skill = self.market_repo.get_or_create_skill(skill_name, category="general")
                self.student_repo.associate_skill(student.id, skill.id)

        return {
            "education_paths_created": paths_created,
            "demo_student_id": demo_student_id,
            "students_seeded": students_created,
        }

    @staticmethod
    def _parse_llm_output(raw: str) -> list:
        text = raw.strip()
        if text.startswith("```"):
            # Strip a markdown code fence (```json ... ```) some models wrap
            # JSON output in despite being told not to.
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BusinessLogicException(f"AI returned an unparseable response: {exc}")
        if not isinstance(data, list):
            raise BusinessLogicException("AI response was not a JSON array as instructed")
        return data
