import json
from sqlalchemy.orm import Session
from core.exceptions import BusinessLogicException, EntityNotFoundException
from domains.student.repository import StudentRepository
from domains.student.models import Student
from domains.market.repository import MarketRepository
from domains.chatbot.service import ChatbotService
from .repository import GuidanceRepository
from .models import EducationPath
from .schemas import EducationPathCreate
from .anti_bias import AntiBiasEngine, RecommendationCandidate
from .seed_data import SEED_EDUCATION_PATHS, SEED_STUDENT
from typing import List

# Distinct from the chatbot domain's conversational persona: this prompt asks
# for a specific, machine-parseable output shape rather than a chat reply.
RECOMMENDATION_SYSTEM_PROMPT = (
    "You are a career-guidance recommendation engine for Vietnamese students. "
    "You will be given a student's inferred profile, their location, a catalog of "
    "available education/training paths (each with a numeric id), and current "
    "job-market trends by career. Choose paths STRICTLY from the given catalog "
    "(reference them by id — never invent a path that isn't listed) and, for each, "
    "write a reasoning_explanation in Vietnamese connecting the student's profile "
    "and the market trend to that specific path. "
    "Present every choice as a reference for the student to weigh, never as a "
    "directive: do not claim any path is the 'correct' or 'only' choice, and do "
    "not base suggestions on the student's gender or hometown. "
    "Respond with ONLY a JSON array, no prose, no markdown code fences, in exactly "
    "this shape: [{\"path_id\": <int>, \"reasoning_explanation\": \"<string>\"}, ...]"
)

class GuidanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GuidanceRepository(db)
        self.student_repo = StudentRepository(db)
        self.market_repo = MarketRepository(db)
        self.chatbot = ChatbotService()
        self.anti_bias = AntiBiasEngine()

    def create_path(self, path: EducationPathCreate) -> EducationPath:
        return self.repo.create_path(path.model_dump())

    def get_all_paths(self) -> List[EducationPath]:
        return self.repo.get_all_paths()

    def get_recommendations(self, student_id: int):
        return self.repo.get_recommendations_by_student(student_id)

    def generate_recommendations(self, student_id: int, count: int = 3):
        student = self.student_repo.get_student(student_id)
        if student is None:
            raise EntityNotFoundException("Student", student_id)

        paths = self.repo.get_all_paths()
        if not paths:
            raise BusinessLogicException("No education paths are configured yet — call /guidance/seed-demo-data or POST /guidance/education-paths/ first")

        careers = self.market_repo.get_careers()

        messages = [
            {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_prompt(student, paths, careers, count)},
        ]
        raw_reply = self.chatbot.complete(messages)
        parsed = self._parse_llm_output(raw_reply)

        paths_by_id = {p.id: p for p in paths}
        candidates = []
        for item in parsed:
            path = paths_by_id.get(item.get("path_id")) if isinstance(item, dict) else None
            reasoning = item.get("reasoning_explanation") if isinstance(item, dict) else None
            if path is not None and isinstance(reasoning, str) and reasoning.strip():
                candidates.append(RecommendationCandidate(path=path, reasoning_explanation=reasoning.strip()))

        if not candidates:
            raise BusinessLogicException("The AI did not return any recommendations matching the available catalog")

        candidates = self.anti_bias.run(candidates, paths, student.current_location)

        return [
            self.repo.create_recommendation({
                "student_id": student_id,
                "path_id": candidate.path.id,
                "reasoning_explanation": candidate.reasoning_explanation,
            })
            for candidate in candidates
        ]

    def seed_demo_data(self):
        """Populates a small education-path catalog and one demo student, so the
        recommendation pipeline is exercisable end-to-end without depending on
        the student domain's (not yet built) own router."""
        paths_created = 0
        for p in SEED_EDUCATION_PATHS:
            existing = self.db.query(EducationPath).filter(EducationPath.name == p["name"]).first()
            if existing is None:
                self.repo.create_path(dict(p))
                paths_created += 1

        student = self.student_repo.get_by_email(SEED_STUDENT["email"])
        student_created = False
        if student is None:
            student = self.student_repo.create_student(dict(SEED_STUDENT))
            student_created = True

        return {
            "education_paths_created": paths_created,
            "demo_student_id": student.id,
            "demo_student_created": student_created,
        }

    @staticmethod
    def _build_prompt(student: Student, paths: List[EducationPath], careers, count: int) -> str:
        profile = json.dumps(student.ai_inferred_profile or {}, ensure_ascii=False)
        catalog = "\n".join(
            f"- id={p.id}, name={p.name}, type={p.type.value}, duration={p.duration}, "
            f"location={p.location or 'remote/nationwide'}, requirements={p.requirements or 'n/a'}"
            for p in paths
        )
        market = "\n".join(f"- {c.title}: {c.market_trend.value}" for c in careers) or "(no market data available yet)"
        return (
            f"Student profile (JSON): {profile}\n"
            f"Student location: {student.current_location or 'unknown'}\n\n"
            f"Available education paths:\n{catalog}\n\n"
            f"Current market trends by career:\n{market}\n\n"
            f"Recommend {count} paths from the catalog above."
        )

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
