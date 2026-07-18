from fastapi import FastAPI
from core.database import Base, engine
from core.config import settings
from domains.market.router import router as market_router
from domains.chatbot.router import router as chatbot_router
from domains.guidance.router import router as guidance_router
from domains.task.router import router as task_router
from domains.task_builder.router import router as task_builder_router
from domains.student.router import router as student_router
from domains.evidence.router import router as evidence_router
from domains.eportfolio.router import router as eportfolio_router

# Import every domain's models so their tables (and any cross-domain
# relationship() targets, e.g. EvidenceClaim -> Skill/Task) are registered on
# Base.metadata / SQLAlchemy's mapper registry, even for domains without a
# router wired up yet. domains/chatbot has none — it's a stateless proxy to
# an external chat API.
from domains.market import models as market_models  # noqa: F401
from domains.student import models as student_models  # noqa: F401
from domains.guidance import models as guidance_models  # noqa: F401
from domains.task import models as task_models  # noqa: F401
from domains.task_builder import models as task_builder_models  # noqa: F401
from domains.evidence import models as evidence_models  # noqa: F401
from domains.eportfolio import models as eportfolio_models  # noqa: F401

# Schema is owned by Alembic (see app/alembic/) — `alembic upgrade head` is
# the only thing that should evolve schema in a shared/production deployment.
# AUTO_CREATE_SCHEMA is a dev/demo convenience on top of that: it fills in any
# missing tables so a fresh local DB works immediately, without requiring a
# manual `alembic upgrade head` first. It's a no-op once the schema already
# matches (create_all only adds missing tables, never alters existing ones),
# so it can't drift the schema the way an unversioned reliance on it used to.
if settings.AUTO_CREATE_SCHEMA:
    Base.metadata.create_all(bind=engine)

tags_metadata = [
    {
        "name": "Market Data",
        "description": "Job market signals extracted from job postings: skill demand, salary ranges, "
                       "and regional growth/shortage trends over time.",
    },
    {
        "name": "Student Profile",
        "description": "Student competency and interest profiles built up through interaction, "
                       "not collapsed into a single personality-test result.",
    },
    {
        "name": "AI Guidance",
        "description": "Personalized, explainable learning and career path recommendations "
                       "(university, vocational, and alternative routes).",
    },
    {
        "name": "AI Chatbot",
        "description": "Conversational assistant that understands a user's needs through dialogue "
                       "and surfaces relevant services — a chat-based front door to guidance.",
    },
    {
        "name": "Task Marketplace",
        "description": "Company-sponsored practical tasks (with sub-tasks) that students complete for "
                       "competency points, through a join → submit → auto-check → mentor-review → complete workflow.",
    },
    {
        "name": "AI Task Builder",
        "description": "Enterprise-facing AI chat that turns a natural-language request and reference "
                       "documents into a structured, mentor-approvable Task.",
    },
    {
        "name": "Evidence",
        "description": "Evidence claims linking a student's task work to a skill, moving from an AI draft "
                       "through student acknowledgement to a mentor's final verify/reject decision.",
    },
    {
        "name": "ePortfolio",
        "description": "Aggregated view of a student's verified skills, evidence, completed tasks, and career "
                       "suggestions — full detail for the student, a consent-gated filtered view for businesses.",
    },
    {
        "name": "Dev Tools",
        "description": "Local development and demo utilities — not part of the production guidance flow.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API phân tích thị trường tuyển dụng và đề xuất lộ trình học tập, "
                 "nghề nghiệp cá nhân hóa cho học sinh/sinh viên.",
    version=settings.VERSION,
    openapi_tags=tags_metadata,
)

app.include_router(market_router)
app.include_router(chatbot_router)
app.include_router(guidance_router)
app.include_router(task_router)
app.include_router(task_builder_router)
app.include_router(student_router)
app.include_router(evidence_router)
app.include_router(eportfolio_router)

@app.get("/")
def read_root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME} API"}
