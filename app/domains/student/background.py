import logging

from core.database import SessionLocal
from domains.student.schemas import RecommendationGenerateRequest
from domains.student.service import StudentProfileService


logger = logging.getLogger(__name__)


def refresh_career_recommendations(student_id: int, limit: int = 5) -> None:
    """Run an LLM recommendation refresh outside the completion request.

    A fresh session is important here: this function runs after the HTTP
    response has started and must not depend on the request-scoped session.
    BackgroundTasks is intentionally best-effort for the demo; a durable
    queue can call this same function later without changing the task flow.
    """
    db = SessionLocal()
    try:
        StudentProfileService(db).generate_student_career_recommendations(
            student_id,
            RecommendationGenerateRequest(limit=limit, persist=True),
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Background career recommendation refresh failed for student_id=%s",
            student_id,
        )
    finally:
        db.close()
