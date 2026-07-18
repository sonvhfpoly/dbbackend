import json
import pytest
from types import SimpleNamespace
from core.exceptions import BusinessLogicException
from domains.task_builder.service import TaskBuilderService
from domains.task_builder.models import ConversationStatus, MessageRole

def make_service(repo=None, task_service=None, chatbot=None):
    """TaskBuilderService.__init__ opens a real DB session — bypass it and
    inject fakes directly, so this stays a pure-logic test (same pattern as
    test_task_service.py). task_service defaults to a fresh FakeTaskService so
    tests that don't care about task creation (most of the start_conversation
    ones) don't each need to pass one just to satisfy resolve_company_id."""
    service = object.__new__(TaskBuilderService)
    service.repo = repo
    service.task_service = task_service if task_service is not None else FakeTaskService()
    service.chatbot = chatbot
    return service

class FakeChatbot:
    """Accepts either a single reply (returned every call) or a list of
    replies (popped in order — used to simulate the retry-after-bad-json
    behavior in TaskBuilderService._complete_and_parse)."""
    def __init__(self, reply):
        self.replies = list(reply) if isinstance(reply, list) else None
        self.reply = reply
        self.calls = []

    def complete(self, messages, json_mode=False):
        self.calls.append(json_mode)
        if self.replies is not None:
            next_reply = self.replies.pop(0)
        else:
            next_reply = self.reply
        if isinstance(next_reply, Exception):
            raise next_reply
        return next_reply

class FakeTaskService:
    """Stands in for domains.task.service.TaskService — generate_task now
    delegates task creation to it (with skip_ai_planning=False, so a
    genuinely broad version can still get auto-split into sub-tasks) instead
    of calling TaskRepository directly, and start_conversation calls
    resolve_company_id before creating the TBConversation."""
    def __init__(self):
        self.created = []
        self._next_id = 500

    def resolve_company_id(self, company_id):
        return company_id if company_id is not None else 999  # 999 = fake placeholder id

    def create_task(self, task_create):
        self._next_id += 1
        task = SimpleNamespace(id=self._next_id, **task_create.model_dump())
        self.created.append(task)
        return task

class FakeTBRepo:
    def __init__(self, conversations=None):
        self.conversations = conversations or {}
        self.all_messages = []
        self._next_conv_id = 1
        self._next_msg_id = 1

    def create_conversation(self, company_id, created_by):
        conv = SimpleNamespace(
            id=self._next_conv_id, company_id=company_id, created_by=created_by,
            status=ConversationStatus.COLLECTING, messages=[], documents=[],
        )
        self.conversations[conv.id] = conv
        self._next_conv_id += 1
        return conv

    def get_conversation(self, conversation_id):
        return self.conversations.get(conversation_id)

    def update_conversation_status(self, conversation_id, status):
        conv = self.conversations.get(conversation_id)
        if conv is not None:
            conv.status = status
        return conv

    def add_message(self, conversation_id, role, content, open_questions=None, proposed_versions=None):
        msg = SimpleNamespace(
            id=self._next_msg_id, conversation_id=conversation_id, role=role, content=content,
            open_questions=open_questions, proposed_versions=proposed_versions,
        )
        self._next_msg_id += 1
        conv = self.conversations.get(conversation_id)
        if conv is not None:
            conv.messages.append(msg)
        self.all_messages.append(msg)
        return msg

    def get_latest_ai_message(self, conversation_id):
        matches = [m for m in self.all_messages if m.conversation_id == conversation_id and m.role == MessageRole.AI]
        return matches[-1] if matches else None

def make_conversation(repo, status=ConversationStatus.COLLECTING, proposed_versions=None):
    conv = repo.create_conversation(company_id=1, created_by="user_enterprise_01")
    conv.status = status
    if proposed_versions is not None:
        repo.add_message(
            conv.id, MessageRole.AI, "reply",
            open_questions=[], proposed_versions=proposed_versions,
        )
    return conv

VERSION_L1 = {
    "version_label": "L1",
    "title": "Dich trich doan 2 trang",
    "context": "Dich tai lieu mo phong sang tieng Viet",
    "complexity_level": "T1",
    "estimated_hours_min": 2,
    "estimated_hours_max": 4,
    "competency_points": 20,
    "scope_included": [],
    "scope_excluded": [],
}

# ---- start_conversation / AI turn parsing ----

def test_start_conversation_collecting_status():
    repo = FakeTBRepo()
    reply = '{"status": "collecting", "reply": "Tai lieu co dung cho muc dich phap ly khong?", "open_questions": ["Muc dich su dung"], "proposed_versions": []}'
    service = make_service(repo=repo, chatbot=FakeChatbot(reply))

    result = service.start_conversation(company_id=1, created_by="user_enterprise_01", message="Toi can dich van ban")

    assert result["status"] == ConversationStatus.COLLECTING
    assert result["open_questions"] == ["Muc dich su dung"]
    assert result["proposed_versions"] == []
    conv = repo.get_conversation(result["conversation_id"])
    assert conv.status == ConversationStatus.COLLECTING
    assert len(conv.messages) == 2  # enterprise turn + ai turn

def test_ai_turn_strips_markdown_fence():
    repo = FakeTBRepo()
    payload = {"status": "ready", "reply": "OK", "open_questions": [], "proposed_versions": [VERSION_L1]}
    reply = "```json\n" + json.dumps(payload) + "\n```"
    service = make_service(repo=repo, chatbot=FakeChatbot(reply))

    result = service.start_conversation(company_id=1, created_by="u1", message="hello")

    assert result["status"] == ConversationStatus.READY
    assert result["proposed_versions"][0]["version_label"] == "L1"

def test_ai_turn_degrades_gracefully_when_both_attempts_return_invalid_json():
    """Regression test: a single malformed AI reply used to raise a 400 and
    leave the conversation stuck (enterprise message persisted, no AI message,
    status unchanged, no way for the client to recover). It must now degrade
    to a fallback AI message instead."""
    repo = FakeTBRepo()
    service = make_service(repo=repo, chatbot=FakeChatbot(["not json at all", "still not json"]))

    result = service.start_conversation(company_id=1, created_by="u1", message="hello")

    assert result["status"] == ConversationStatus.COLLECTING  # unchanged, not raised
    assert result["open_questions"] == []
    assert result["proposed_versions"] == []
    conv = repo.get_conversation(result["conversation_id"])
    assert len(conv.messages) == 2  # enterprise turn + fallback AI turn — nothing lost
    assert conv.messages[-1].role == MessageRole.AI

def test_ai_turn_retries_once_and_recovers_on_second_valid_json():
    repo = FakeTBRepo()
    valid = '{"status": "collecting", "reply": "OK", "open_questions": ["Muc dich?"], "proposed_versions": []}'
    chatbot = FakeChatbot(["not json at all", valid])
    service = make_service(repo=repo, chatbot=chatbot)

    result = service.start_conversation(company_id=1, created_by="u1", message="hello")

    assert result["status"] == ConversationStatus.COLLECTING
    assert result["open_questions"] == ["Muc dich?"]
    assert len(chatbot.calls) == 2  # first attempt + one corrective retry, not more

def test_ai_turn_requests_json_mode_from_provider():
    repo = FakeTBRepo()
    valid = '{"status": "collecting", "reply": "OK", "open_questions": [], "proposed_versions": []}'
    chatbot = FakeChatbot(valid)
    service = make_service(repo=repo, chatbot=chatbot)

    service.start_conversation(company_id=1, created_by="u1", message="hello")

    assert chatbot.calls == [True]  # json_mode=True, no retry needed

def test_ai_turn_forces_finalize_after_max_clarifying_questions():
    """Regression test: after MAX_CLARIFYING_QUESTIONS (3) rounds of questions,
    the next turn must inject QUESTION_LIMIT_INSTRUCTION so the AI can't keep
    asking indefinitely."""
    from domains.task_builder.service import MAX_CLARIFYING_QUESTIONS, QUESTION_LIMIT_INSTRUCTION

    repo = FakeTBRepo()
    conv = repo.create_conversation(company_id=1, created_by="u1")
    for i in range(MAX_CLARIFYING_QUESTIONS):
        repo.add_message(conv.id, MessageRole.ENTERPRISE, f"answer {i}")
        repo.add_message(conv.id, MessageRole.AI, f"question {i}", open_questions=[f"q{i}"], proposed_versions=[])
    repo.add_message(conv.id, MessageRole.ENTERPRISE, "one more answer")

    valid = '{"status": "ready", "reply": "OK", "open_questions": [], "proposed_versions": [' + json.dumps(VERSION_L1) + ']}'
    chatbot = FakeChatbot(valid)
    service = make_service(repo=repo, chatbot=chatbot)

    result = service._run_ai_turn(conv.id)

    ai_messages = service._build_ai_messages(repo.get_conversation(conv.id))
    assert result["status"] == ConversationStatus.READY
    # The instruction wasn't present yet for the first 3 rounds, only once the cap is reached.
    assert any(m["content"] == QUESTION_LIMIT_INSTRUCTION for m in ai_messages)

def test_add_message_with_confirm_forces_finalize_instruction():
    """Regression test: an enterprise confirming early (confirm=True) must get
    USER_CONFIRMED_INSTRUCTION injected immediately, even on the very first
    reply — they shouldn't have to wait for MAX_CLARIFYING_QUESTIONS rounds."""
    from domains.task_builder.service import USER_CONFIRMED_INSTRUCTION

    repo = FakeTBRepo()
    conv = make_conversation(repo, status=ConversationStatus.COLLECTING)
    repo.add_message(conv.id, MessageRole.AI, "question 0", open_questions=["q0"], proposed_versions=[])
    valid = '{"status": "ready", "reply": "OK", "open_questions": [], "proposed_versions": [' + json.dumps(VERSION_L1) + ']}'
    chatbot = FakeChatbot(valid)
    service = make_service(repo=repo, chatbot=chatbot)

    result = service.add_message(conv.id, "tạo task luôn đi", confirm=True)

    assert result["status"] == ConversationStatus.READY
    ai_messages = service._build_ai_messages(repo.get_conversation(conv.id), force_finalize=True)
    assert any(m["content"] == USER_CONFIRMED_INSTRUCTION for m in ai_messages)

def test_generate_task_fills_missing_optional_fields_with_defaults():
    """A confirmed/incomplete proposal (missing complexity_level/hours/points,
    but title+context present) must still create a task instead of blocking —
    the whole point of confirm=True is not requiring a fully-detailed brief."""
    repo = FakeTBRepo()
    incomplete = dict(VERSION_L1)
    for field in ("complexity_level", "estimated_hours_min", "estimated_hours_max", "competency_points"):
        incomplete.pop(field)
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[incomplete])
    task_service = FakeTaskService()
    service = make_service(repo=repo, task_service=task_service)

    result = service.generate_task(conv.id, "L1")

    created = task_service.created[0]
    assert created.complexity_level.value == "T1"
    assert created.estimated_hours_min == 1
    assert created.estimated_hours_max == 4
    assert created.competency_points == 10
    assert result["status"] == ConversationStatus.TASK_CREATED

def test_build_ai_messages_omits_question_limit_instruction_before_cap():
    repo = FakeTBRepo()
    conv = repo.create_conversation(company_id=1, created_by="u1")
    repo.add_message(conv.id, MessageRole.ENTERPRISE, "answer 0")
    repo.add_message(conv.id, MessageRole.AI, "question 0", open_questions=["q0"], proposed_versions=[])
    service = make_service(repo=repo, chatbot=None)

    from domains.task_builder.service import QUESTION_LIMIT_INSTRUCTION
    ai_messages = service._build_ai_messages(repo.get_conversation(conv.id))

    assert not any(m["content"] == QUESTION_LIMIT_INSTRUCTION for m in ai_messages)

def test_start_conversation_resolves_missing_company_id_instead_of_failing():
    """Regression test: starting a conversation without a company_id (or with
    one that isn't registered) must not hard-fail — it resolves to a
    placeholder company via TaskService.resolve_company_id."""
    repo = FakeTBRepo()
    reply = '{"status": "collecting", "reply": "OK", "open_questions": [], "proposed_versions": []}'
    service = make_service(repo=repo, chatbot=FakeChatbot(reply))

    result = service.start_conversation(company_id=None, created_by="u1", message="hello")

    conv = repo.get_conversation(result["conversation_id"])
    assert conv.company_id == 999  # placeholder, not None and not an error

# ---- open questions (read-only) ----

def test_get_open_questions_reads_latest_ai_message_without_calling_ai():
    repo = FakeTBRepo()
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[VERSION_L1])
    service = make_service(repo=repo, chatbot=None)  # no chatbot needed — must not be called

    result = service.get_open_questions(conv.id)

    assert result["status"] == ConversationStatus.READY
    assert result["proposed_versions"] == [VERSION_L1]

# ---- generate_task ----

def test_generate_task_rejects_when_not_ready():
    repo = FakeTBRepo()
    conv = make_conversation(repo, status=ConversationStatus.COLLECTING)
    service = make_service(repo=repo, task_service=FakeTaskService())

    with pytest.raises(BusinessLogicException):
        service.generate_task(conv.id, "L1")

def test_generate_task_rejects_unknown_version():
    repo = FakeTBRepo()
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[VERSION_L1])
    service = make_service(repo=repo, task_service=FakeTaskService())

    with pytest.raises(BusinessLogicException):
        service.generate_task(conv.id, "L2")

def test_generate_task_rejects_missing_required_field():
    repo = FakeTBRepo()
    incomplete = dict(VERSION_L1)
    incomplete.pop("context")
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[incomplete])
    service = make_service(repo=repo, task_service=FakeTaskService())

    with pytest.raises(BusinessLogicException):
        service.generate_task(conv.id, "L1")

def test_generate_task_creates_exactly_one_task():
    repo = FakeTBRepo()
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[VERSION_L1])
    task_service = FakeTaskService()
    service = make_service(repo=repo, task_service=task_service)

    result = service.generate_task(conv.id, "L1")

    assert len(task_service.created) == 1
    created = task_service.created[0]
    assert created.title == VERSION_L1["title"]
    assert created.company_id == conv.company_id
    assert result["status"] == ConversationStatus.TASK_CREATED
    assert result["created_task"] is created
    assert conv.status == ConversationStatus.TASK_CREATED
    # A confirmation message was appended to the transcript.
    assert conv.messages[-1].role == MessageRole.AI

def test_generate_task_passes_through_deadline_when_ai_proposed_one():
    repo = FakeTBRepo()
    version_with_deadline = dict(VERSION_L1, deadline="2026-08-01T00:00:00")
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[version_with_deadline])
    task_service = FakeTaskService()
    service = make_service(repo=repo, task_service=task_service)

    service.generate_task(conv.id, "L1")

    assert str(task_service.created[0].deadline) == "2026-08-01 00:00:00"

def test_generate_task_deadline_defaults_to_none_when_not_mentioned():
    repo = FakeTBRepo()
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[VERSION_L1])
    task_service = FakeTaskService()
    service = make_service(repo=repo, task_service=task_service)

    service.generate_task(conv.id, "L1")

    assert task_service.created[0].deadline is None

def test_generate_task_enables_ai_planning_for_sub_task_splitting():
    """Regression test: generate_task used to hardcode skip_ai_planning=True,
    so a task created from the AI Task Builder could never get auto-split
    into sub-tasks — the only capability that ever exercised that path was
    the seed-demo-data script. Enabled per explicit request so a genuinely
    broad AI-Task-Builder version can still be split, same as a manually
    created task would."""
    repo = FakeTBRepo()
    conv = make_conversation(repo, status=ConversationStatus.READY, proposed_versions=[VERSION_L1])
    task_service = FakeTaskService()
    service = make_service(repo=repo, task_service=task_service)

    service.generate_task(conv.id, "L1")

    assert task_service.created[0].skip_ai_planning is False
