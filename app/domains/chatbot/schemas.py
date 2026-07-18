from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ChatRole(str, Enum):
    user = "user"
    assistant = "assistant"

class ChatMessage(BaseModel):
    role: ChatRole
    content: str

class ChatRequest(BaseModel):
    message: str = Field(description="The user's latest message", examples=["Em thích vẽ và làm việc với máy tính, nên học ngành gì?"])
    # System prompt is fixed server-side (see service.py) so callers can't
    # override the assistant's behavior/guardrails from the request body.
    history: List[ChatMessage] = Field(default_factory=list, description="Prior turns, oldest first, without the system message")

class ChatResponse(BaseModel):
    reply: str
    model: str
    model_config = ConfigDict(from_attributes=True)

class ChatbotHealth(BaseModel):
    configured: bool = Field(description="Whether the active AI provider is configured for this environment")
    reachable: Optional[bool] = Field(default=None, description="Result of a live upstream call; null unless ?deep=true was requested")
    provider: str = Field(description="Which AI provider is active: 'vertex_ai' or 'fpt_cloud'")
    model: str
