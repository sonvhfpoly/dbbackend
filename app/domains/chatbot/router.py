from fastapi import APIRouter, Depends
from .schemas import ChatRequest, ChatResponse, ChatbotHealth
from .service import ChatbotService

router = APIRouter(
    prefix="/assistant",
    tags=["AI Chatbot"],
)

def get_chatbot_service() -> ChatbotService:
    return ChatbotService()

@router.post("/chat", response_model=ChatResponse, summary="Chat with the career-guidance assistant")
def chat(request: ChatRequest, service: ChatbotService = Depends(get_chatbot_service)):
    reply = service.chat(request.message, request.history)
    return ChatResponse(reply=reply, model=service.model)

@router.get(
    "/health",
    response_model=ChatbotHealth,
    summary="Check whether the chatbot integration is configured (and optionally reachable)",
    description="?deep=true makes a real, minimal upstream call to verify connectivity — "
                "off by default so routine health polling doesn't burn API quota/latency.",
)
def health(deep: bool = False, service: ChatbotService = Depends(get_chatbot_service)):
    configured, reachable = service.check_health(deep=deep)
    return ChatbotHealth(configured=configured, reachable=reachable, provider=service.provider_name, model=service.model)
