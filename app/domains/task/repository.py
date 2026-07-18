from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from .models import (
    Company, Task, TaskInput, TaskOutput, TaskEvaluationCriterion,
    TaskSubmission, TaskSubmissionScore, TaskReview, TaskSubmissionFile, TaskSkill,
)

class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- Company ----

    def get_or_create_company(self, data: dict) -> Company:
        company = self.db.query(Company).filter(Company.slug == data["slug"]).first()
        if company is None:
            company = Company(**data)
            self.db.add(company)
            self.db.commit()
            self.db.refresh(company)
        return company

    def get_company(self, company_id: int) -> Optional[Company]:
        return self.db.query(Company).filter(Company.id == company_id).first()

    def list_companies(self) -> List[Company]:
        return self.db.query(Company).all()

    # ---- Task ----

    def create_task(self, data: dict) -> Task:
        inputs_data = data.pop("inputs", [])
        outputs_data = data.pop("outputs", [])
        criteria_data = data.pop("criteria", [])
        skill_ids = data.pop("skill_ids", [])

        task = Task(**data)
        task.inputs = [TaskInput(**d) for d in inputs_data]
        task.outputs = [TaskOutput(**d) for d in outputs_data]
        task.criteria = [TaskEvaluationCriterion(**d) for d in criteria_data]
        if skill_ids:
            # Lazy import keeps the task repository independent from the
            # market repository while still validating the FK targets.
            from domains.market.models import Skill
            task.skills = self.db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
            found_ids = {skill.id for skill in task.skills}
            missing_ids = set(skill_ids) - found_ids
            if missing_ids:
                raise ValueError(f"Unknown skill_ids: {sorted(missing_ids)}")

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def set_task_skills(self, task: Task, skill_ids: List[int]) -> Task:
        from domains.market.models import Skill
        skills = self.db.query(Skill).filter(Skill.id.in_(skill_ids)).all() if skill_ids else []
        found_ids = {skill.id for skill in skills}
        missing_ids = set(skill_ids) - found_ids
        if missing_ids:
            raise ValueError(f"Unknown skill_ids: {sorted(missing_ids)}")
        task.skills = skills
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_task_by_title(self, title: str) -> Optional[Task]:
        return self.db.query(Task).filter(Task.title == title).first()

    def list_tasks(
        self,
        complexity_level: Optional[str] = None,
        company_id: Optional[int] = None,
        root_only: bool = True,
        review_status: Optional[str] = None,
    ) -> List[Task]:
        query = self.db.query(Task)
        if root_only:
            query = query.filter(Task.parent_task_id.is_(None))
        if complexity_level:
            query = query.filter(Task.complexity_level == complexity_level)
        if company_id:
            query = query.filter(Task.company_id == company_id)
        if review_status:
            query = query.filter(Task.review_status == review_status)
        return query.order_by(Task.created_at.desc()).all()

    def get_sub_tasks(self, parent_task_id: int) -> List[Task]:
        return (
            self.db.query(Task)
            .filter(Task.parent_task_id == parent_task_id)
            .order_by(Task.sort_order)
            .all()
        )

    def update_task(self, task_id: int, **fields) -> Optional[Task]:
        task = self.get_task(task_id)
        if task is None:
            return None
        for key, value in fields.items():
            setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task_row(self, task: Task) -> None:
        """Deletes exactly this row. inputs/outputs/criteria/reviews cascade
        via their relationship(cascade="all, delete-orphan") on Task — but
        sub_tasks and task_submissions don't, so the caller (TaskService.delete_task)
        must clear those explicitly first, in child-before-parent order."""
        self.db.delete(task)
        self.db.commit()

    def count_submissions_for_task(self, task_id: int) -> int:
        return self.db.query(TaskSubmission).filter(TaskSubmission.task_id == task_id).count()

    def delete_submissions_for_task(self, task_id: int) -> None:
        # One-by-one (not a bulk query().delete()) so TaskSubmission's own
        # cascade="all, delete-orphan" on scores/files actually fires.
        submissions = self.db.query(TaskSubmission).filter(TaskSubmission.task_id == task_id).all()
        for submission in submissions:
            self.db.delete(submission)
        self.db.commit()

    def count_evidence_claims_for_task(self, task_id: int) -> int:
        # Lazy import: evidence is a separate domain and this is the only
        # place task/repository.py needs to reach into it.
        from domains.evidence.models import EvidenceClaim
        return self.db.query(EvidenceClaim).filter(EvidenceClaim.task_id == task_id).count()

    # ---- Task <-> Skill linking ----

    def get_task_skill_ids(self, task_id: int) -> List[int]:
        return [
            row[0] for row in
            self.db.query(TaskSkill.skill_id).filter(TaskSkill.task_id == task_id).all()
        ]

    def link_task_skill(self, task_id: int, skill_id: int) -> None:
        self.db.merge(TaskSkill(task_id=task_id, skill_id=skill_id))  # merge avoids dup on re-link
        self.db.commit()

    # ---- Task review ----

    def create_task_review(self, task_id: int, data: dict) -> TaskReview:
        review = TaskReview(task_id=task_id, **data)
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def list_task_reviews(self, task_id: int) -> List[TaskReview]:
        return (
            self.db.query(TaskReview)
            .filter(TaskReview.task_id == task_id)
            .order_by(TaskReview.created_at.desc())
            .all()
        )

    # ---- Submission ----

    def create_submission(self, task_id: int, student_id: int) -> TaskSubmission:
        submission = TaskSubmission(task_id=task_id, student_id=student_id)
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def get_submission(self, submission_id: int) -> Optional[TaskSubmission]:
        return self.db.query(TaskSubmission).filter(TaskSubmission.id == submission_id).first()

    def get_latest_submission(self, task_id: int, student_id: int) -> Optional[TaskSubmission]:
        return (
            self.db.query(TaskSubmission)
            .filter(TaskSubmission.task_id == task_id, TaskSubmission.student_id == student_id)
            .order_by(TaskSubmission.joined_at.desc())
            .first()
        )

    def update_submission(self, submission_id: int, **fields) -> Optional[TaskSubmission]:
        submission = self.get_submission(submission_id)
        if submission is None:
            return None
        for key, value in fields.items():
            setattr(submission, key, value)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def list_submissions(self, task_id: Optional[int] = None, student_id: Optional[int] = None) -> List[TaskSubmission]:
        query = self.db.query(TaskSubmission)
        if task_id is not None:
            query = query.filter(TaskSubmission.task_id == task_id)
        if student_id is not None:
            query = query.filter(TaskSubmission.student_id == student_id)
        return query.all()

    # ---- Scoring ----

    def upsert_score(self, submission_id: int, criterion_id: int, score_percent: int, feedback: Optional[str], scored_by) -> TaskSubmissionScore:
        """Re-scoring the same criterion updates the existing row instead of
        creating a duplicate — a criterion should have one current score per
        submission, not a growing history of re-grades."""
        score = (
            self.db.query(TaskSubmissionScore)
            .filter(
                TaskSubmissionScore.submission_id == submission_id,
                TaskSubmissionScore.criterion_id == criterion_id,
            )
            .first()
        )
        if score is None:
            score = TaskSubmissionScore(submission_id=submission_id, criterion_id=criterion_id)
            self.db.add(score)

        score.score_percent = score_percent
        score.feedback = feedback
        score.scored_by = scored_by
        score.scored_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(score)
        return score

    def get_scores_for_submission(self, submission_id: int) -> List[TaskSubmissionScore]:
        return self.db.query(TaskSubmissionScore).filter(TaskSubmissionScore.submission_id == submission_id).all()

    # ---- Submission files ----

    def count_submission_files(self, submission_id: int) -> int:
        return self.db.query(TaskSubmissionFile).filter(TaskSubmissionFile.submission_id == submission_id).count()

    def create_submission_file(self, submission_id: int, data: dict) -> TaskSubmissionFile:
        file = TaskSubmissionFile(submission_id=submission_id, **data)
        self.db.add(file)
        self.db.commit()
        self.db.refresh(file)
        return file

    def list_submission_files(self, submission_id: int) -> List[TaskSubmissionFile]:
        return (
            self.db.query(TaskSubmissionFile)
            .filter(TaskSubmissionFile.submission_id == submission_id)
            .order_by(TaskSubmissionFile.uploaded_at.asc())
            .all()
        )
