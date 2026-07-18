from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from .models import (
    Company, Task, TaskInput, TaskOutput, TaskEvaluationCriterion,
    TaskSubmission, TaskSubmissionScore, TaskReview, TaskSubmissionFile,
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

        task = Task(**data)
        task.inputs = [TaskInput(**d) for d in inputs_data]
        task.outputs = [TaskOutput(**d) for d in outputs_data]
        task.criteria = [TaskEvaluationCriterion(**d) for d in criteria_data]

        self.db.add(task)
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
        return query.all()

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
