from typing import List, Optional, Tuple
import requests
from fastapi import HTTPException, status
from core.config import settings
from .schemas import ChatMessage

# Fixed server-side so a client can't smuggle in a different persona via the
# request body; matches the "expand choices, don't gatekeep" tone the
# guidance domain's recommendations are also expected to follow.
SYSTEM_PROMPT = (
    "You are a helpful assistant capable of understanding a user's needs through "
    "conversation to recommend suitable services. Based on the conversation history "
    "and the user's last message, list services that can address the user's needs. "
    "Respond only in Vietnamese or English, matching the language of the user's input."
)

CHAT_TIMEOUT_SECONDS = 30
HEALTH_CHECK_TIMEOUT_SECONDS = 10

class ChatbotService:
    """Thin client for FPT Cloud's OpenAI-compatible chat-completions endpoint."""

    def __init__(self):
        self._url = f"{settings.FPT_CLOUD_BASE_URL.rstrip('/')}/chat/completions"

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.FPT_CLOUD_API_KEY}",
        }

    def chat(self, message: str, history: List[ChatMessage]) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": h.role.value, "content": h.content} for h in history]
        messages.append({"role": "user", "content": message})
        return self.complete(messages)

    def complete(self, messages: List[dict]) -> str:
        """Single-turn (or pre-built multi-turn) completion for callers that need
        a different persona/task than the general assistant in chat() — e.g. the
        guidance domain's recommendation engine, which needs structured JSON back
        rather than a conversational reply. Takes raw OpenAI-style message dicts
        so callers control the system prompt directly."""
        if not settings.FPT_CLOUD_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chatbot is not configured: FPT_CLOUD_API_KEY is missing",
            )

        payload = {
            "model": settings.FPT_CLOUD_CHAT_MODEL,
            "messages": messages,
            # Non-streaming: this endpoint is called from a plain request/response
            # route (and tested via Swagger "Try it out"), which can't consume a
            # server-sent-event stream. Streaming to the client would need a
            # StreamingResponse pass-through instead — not needed for this use case.
            "stream": False,
        }

        try:
            # requests is sync/blocking; the router calls this from a sync `def`
            # route so FastAPI runs it in a worker thread instead of blocking
            # the event loop.
            response = requests.post(self._url, headers=self._headers(), json=payload, timeout=CHAT_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.HTTPError as exc:
            # str(exc) is just the status line ("403 Client Error: Forbidden for
            # url: ..."); the response body is where the gateway actually says
            # *why* (bad key, model not entitled, quota exceeded, etc.).
            body = exc.response.text[:500] if exc.response is not None else ""
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Chatbot upstream error: {exc} — body: {body}",
            ) from exc
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Chatbot upstream request failed: {exc}",
            ) from exc

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Chatbot upstream returned an unexpected response shape",
            ) from exc

    def check_health(self, deep: bool = False) -> Tuple[bool, Optional[bool]]:
        """`deep=False` (default) only checks that a key is configured — free and
        instant, safe for frequent polling. `deep=True` makes a real (paid,
        slower) upstream call, so it's opt-in rather than the default."""
        configured = bool(settings.FPT_CLOUD_API_KEY)
        if not deep or not configured:
            return configured, None

        payload = {
            "model": settings.FPT_CLOUD_CHAT_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
            "max_tokens": 1,
        }
        try:
            response = requests.post(self._url, headers=self._headers(), json=payload, timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
            reachable = response.ok
        except requests.RequestException:
            reachable = False

        return configured, reachable
