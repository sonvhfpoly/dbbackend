from typing import List, Optional, Tuple

from .providers import get_active_provider
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


class ChatbotService:
    """Thin facade over whichever AIProvider is active for this process —
    Vertex AI on Cloud Run, or FPT Cloud otherwise (see providers.py). Callers
    (router, task/service.py, guidance/service.py) don't need to know which
    one is answering."""

    def __init__(self):
        self._provider = get_active_provider()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._provider.model

    def chat(self, message: str, history: List[ChatMessage]) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": h.role.value, "content": h.content} for h in history]
        messages.append({"role": "user", "content": message})
        return self.complete(messages)

    def complete(self, messages: List[dict], json_mode: bool = False) -> str:
        """Single-turn (or pre-built multi-turn) completion for callers that need
        a different persona/task than the general assistant in chat() — e.g. the
        guidance domain's recommendation engine, which needs structured JSON back
        rather than a conversational reply. Takes raw OpenAI-style message dicts
        so callers control the system prompt directly. json_mode=True constrains
        the reply to a JSON object at the provider/API level (see providers.py) —
        set it whenever the caller is going to json.loads() the result."""
        return self._provider.complete(messages, json_mode=json_mode)

    def check_health(self, deep: bool = False) -> Tuple[bool, Optional[bool]]:
        return self._provider.check_health(deep=deep)
