from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List, Optional, Tuple

import google.auth
import requests
from fastapi import HTTPException, status
from google import genai
from google.genai import types

from core.config import settings

CHAT_TIMEOUT_SECONDS = 30
HEALTH_CHECK_TIMEOUT_SECONDS = 10


class AIProvider(ABC):
    """A configured, ready-to-call AI backend. `name` and `model` are surfaced
    in /assistant/health and chat responses so callers can see which backend
    actually answered."""

    name: str
    model: str

    @abstractmethod
    def complete(self, messages: List[dict]) -> str:
        """messages is a list of OpenAI-style {"role", "content"} dicts
        (system/user/assistant); returns the reply text."""

    @abstractmethod
    def check_health(self, deep: bool = False) -> Tuple[bool, Optional[bool]]: ...


class FPTCloudProvider(AIProvider):
    """FPT Cloud Marketplace's OpenAI-compatible chat-completions endpoint,
    authenticated with a static API key. Used when Vertex AI isn't available
    (e.g. running outside Cloud Run without `gcloud auth application-default
    login`)."""

    name = "fpt_cloud"

    def __init__(self):
        self.model = settings.FPT_CLOUD_CHAT_MODEL
        self._url = f"{settings.FPT_CLOUD_BASE_URL.rstrip('/')}/chat/completions"

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.FPT_CLOUD_API_KEY}",
        }

    def complete(self, messages: List[dict]) -> str:
        if not settings.FPT_CLOUD_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chatbot is not configured: FPT_CLOUD_API_KEY is missing",
            )

        payload = {
            "model": self.model,
            "messages": messages,
            # Non-streaming: this endpoint is called from a plain request/response
            # route, which can't consume a server-sent-event stream.
            "stream": False,
        }

        try:
            # requests is sync/blocking; callers run this from a sync `def`
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
            "model": self.model,
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


class VertexAIProvider(AIProvider):
    """Google Cloud Vertex AI (Gemini), authenticated via Application Default
    Credentials — on Cloud Run this is the service account attached to the
    service, loaded automatically with no key to manage."""

    name = "vertex_ai"

    def __init__(self, project: str):
        self.model = settings.VERTEX_MODEL
        self._client = genai.Client(vertexai=True, project=project, location=settings.VERTEX_LOCATION)

    def complete(self, messages: List[dict]) -> str:
        # Gemini takes the system prompt separately from the turn history, and
        # uses "model" rather than "assistant" for the assistant's own turns.
        system_instruction = "\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
            if m["role"] != "system"
        ]

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_instruction or None),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Vertex AI upstream error: {exc}",
            ) from exc

        if not response.text:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Vertex AI upstream returned an unexpected response shape",
            )
        return response.text

    def check_health(self, deep: bool = False) -> Tuple[bool, Optional[bool]]:
        # Selection into this provider already implies ADC + project were
        # found, so "configured" is unconditionally true here.
        if not deep:
            return True, None
        try:
            self.complete([{"role": "user", "content": "ping"}])
            reachable = True
        except HTTPException:
            reachable = False
        return True, reachable


def _detect_vertex_project() -> Optional[str]:
    if settings.VERTEX_PROJECT_ID:
        return settings.VERTEX_PROJECT_ID
    try:
        _, project = google.auth.default()
        return project
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_active_provider() -> AIProvider:
    """Vertex AI is preferred whenever Application Default Credentials and a
    project can be resolved (always true on Cloud Run with the service
    account attached; also true locally after `gcloud auth
    application-default login`). Otherwise falls back to the FPT Cloud
    API-key mechanism, unchanged from before Vertex AI existed.

    Decided once per process lifetime (cached) rather than per-request:
    cheap, but means a Vertex AI outage/misconfiguration discovered after
    this first check (e.g. API not enabled, missing IAM role) surfaces as
    request-time errors rather than an automatic switch to FPT Cloud.
    """
    project = _detect_vertex_project()
    if project:
        try:
            return VertexAIProvider(project=project)
        except Exception:
            pass
    return FPTCloudProvider()
