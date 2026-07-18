from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from domains.task.schemas import TaskComplexity, TaskRead
# Re-exported (not redefined) — see market/schemas.py for why.
from .models import ConversationStatus, MessageRole  # noqa: F401

# ---- Conversation lifecycle ----

class TBConversationCreate(BaseModel):
    company_id: Optional[int] = Field(default=None, description="Omit (or pass an id that isn't registered) to fall back to a shared placeholder company — starting a conversation never fails for a missing/invalid company.")
    created_by: str = Field(description="Caller-supplied identifier for whoever is running this conversation")
    message: str = Field(description="The enterprise's opening request")

class TBMessageCreate(BaseModel):
    message: str
    confirm: bool = Field(
        default=False,
        description="Enterprise explicitly confirms creating the task now, even with incomplete "
                    "details — the AI stops asking clarifying questions and proposes a version "
                    "immediately, filling any gaps with reasonable defaults instead of requiring a "
                    "fully-detailed brief.",
    )

class ProposedVersion(BaseModel):
    version_label: str = Field(description="e.g. 'L1', 'L2' — matched against generate-task's selected_version")
    title: str
    context: str
    complexity_level: TaskComplexity
    estimated_hours_min: int
    estimated_hours_max: int
    competency_points: int
    scope_included: List[str] = Field(default_factory=list)
    scope_excluded: List[str] = Field(default_factory=list)
    deadline: Optional[datetime] = Field(default=None, description="Enterprise's desired completion date, if mentioned in the brief (requirements.md §7.1).")

class TaskBuilderTurn(BaseModel):
    """What every conversation-advancing call (start/add message) returns."""
    conversation_id: int
    status: ConversationStatus
    reply: str = Field(description="The AI's natural-language reply for this turn")
    open_questions: List[str] = Field(default_factory=list, description="Questions the AI still needs answered before it can propose task versions")
    proposed_versions: List[ProposedVersion] = Field(default_factory=list, description="Only populated once status='READY'")

class OpenQuestionsRead(BaseModel):
    """Read-only view of the latest turn's state — no AI call, straight from DB."""
    conversation_id: int
    status: ConversationStatus
    open_questions: List[str] = Field(default_factory=list)
    proposed_versions: List[ProposedVersion] = Field(default_factory=list)

# ---- Messages / documents (for GET conversation detail) ----

class TBMessageRead(BaseModel):
    id: int
    role: MessageRole
    content: str
    open_questions: Optional[List[str]] = None
    proposed_versions: Optional[List[ProposedVersion]] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TBDocumentRead(BaseModel):
    id: int
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    storage_url: str
    extracted_text_length: int = 0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TBConversationRead(BaseModel):
    id: int
    company_id: int
    created_by: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    messages: List[TBMessageRead] = Field(default_factory=list)
    documents: List[TBDocumentRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

# ---- Task generation ----

class GenerateTaskRequest(BaseModel):
    selected_version: str = Field(description="version_label from the latest proposed_versions, e.g. 'L1'")

class GenerateTaskResult(BaseModel):
    conversation_id: int
    status: ConversationStatus
    created_task: TaskRead
    ai_message: str
