from fastapi import FastAPI
from core.database import Base, engine
from core.config import settings
from domains.market.router import router as market_router
from domains.chatbot.router import router as chatbot_router
from domains.guidance.router import router as guidance_router
from domains.task.router import router as task_router
from domains.task_builder.router import router as task_builder_router

# Import every domain's models so their tables are registered on Base.metadata
# before create_all runs, even for domains without a router wired up yet.
# domains/chatbot has none — it's a stateless proxy to an external chat API.
from domains.market import models as market_models  # noqa: F401
from domains.student import models as student_models  # noqa: F401
from domains.guidance import models as guidance_models  # noqa: F401
from domains.task import models as task_models  # noqa: F401
from domains.task_builder import models as task_builder_models  # noqa: F401

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

@app.get("/")
def read_root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME} API"}
