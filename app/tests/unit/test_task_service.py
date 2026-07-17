import pytest
from types import SimpleNamespace
from core.exceptions import BusinessLogicException
from domains.task.service import TaskService
from domains.task.models import SubmissionStatus, TaskDifficulty

def make_service(repo, chatbot=None):
    """TaskService.__init__ opens a real DB session via TaskRepository(db) —
    bypass it and inject a fake repo directly, so this stays a pure-logic test."""
    service = object.__new__(TaskService)
    service.repo = repo
    service.chatbot = chatbot
    return service

def make_task(id, parent_task_id=None):
    return SimpleNamespace(id=id, parent_task_id=parent_task_id)

class FakeRepo:
    def __init__(self, tasks=None, sub_tasks=None, submissions=None):
        self.tasks = tasks or {}
        self.sub_tasks = sub_tasks or {}
        # submissions: dict[(task_id, student_id)] -> SimpleNamespace(status=..., points_awarded=...)
        self.submissions = submissions or {}
        self.created_tasks = []
        self._next_id = 1000

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def get_sub_tasks(self, parent_task_id):
        return self.sub_tasks.get(parent_task_id, [])

    def get_latest_submission(self, task_id, student_id):
        return self.submissions.get((task_id, student_id))

    def create_task(self, data):
        self._next_id += 1
        task = SimpleNamespace(id=self._next_id, **data)
        self.created_tasks.append(task)
        self.tasks[task.id] = task  # so a later get_task/update_task can find it, like a real DB
        return task

    def update_task(self, task_id, **fields):
        task = self.tasks.get(task_id)
        if task is None:
            return None
        for key, value in fields.items():
            setattr(task, key, value)
        return task

class FakeChatbot:
    def __init__(self, reply):
        self.reply = reply

    def complete(self, messages):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

def make_root_task(id=1):
    return SimpleNamespace(
        id=id, title="Phan tich hanh vi khach hang", parent_task_id=None, difficulty=TaskDifficulty.MEDIUM,
        company_id=1, context="Phan tich du lieu", scope_included=[], scope_excluded=[],
        estimated_hours_min=5, estimated_hours_max=10, competency_points=50,
    )

# ---- AI sub-task planning ----

def test_ai_plan_subtasks_creates_subtasks_and_nulls_parent_points_when_should_split():
    task = make_root_task()
    repo = FakeRepo(tasks={task.id: task})
    reply = '{"difficulty": "HARD", "should_split": true, "sub_tasks": [' \
            '{"title": "Sub 1", "context": "ctx 1", "estimated_hours_min": 2, "estimated_hours_max": 4, "competency_points": 20, "difficulty": "EASY"}, ' \
            '{"title": "Sub 2", "context": "ctx 2", "estimated_hours_min": 3, "estimated_hours_max": 5, "competency_points": 30, "difficulty": "MEDIUM"}' \
            ']}'
    service = make_service(repo, chatbot=FakeChatbot(reply))

    service._ai_plan_subtasks(task)

    assert len(repo.created_tasks) == 2
    assert all(t.parent_task_id == task.id for t in repo.created_tasks)
    assert task.difficulty == TaskDifficulty.HARD
    assert task.competency_points is None  # rolled up from sub-tasks now

def test_ai_plan_subtasks_noop_when_should_split_false():
    task = make_root_task()
    repo = FakeRepo(tasks={task.id: task})
    reply = '{"difficulty": "MEDIUM", "should_split": false, "sub_tasks": []}'
    service = make_service(repo, chatbot=FakeChatbot(reply))

    service._ai_plan_subtasks(task)

    assert repo.created_tasks == []
    assert task.competency_points == 50  # untouched — no split happened

def test_ai_plan_subtasks_swallows_chatbot_errors():
    task = make_root_task()
    repo = FakeRepo(tasks={task.id: task})
    service = make_service(repo, chatbot=FakeChatbot(RuntimeError("upstream down")))

    service._ai_plan_subtasks(task)  # must not raise

    assert repo.created_tasks == []
    assert task.competency_points == 50

def test_ai_plan_subtasks_swallows_unparseable_reply():
    task = make_root_task()
    repo = FakeRepo(tasks={task.id: task})
    service = make_service(repo, chatbot=FakeChatbot("not json at all"))

    service._ai_plan_subtasks(task)  # must not raise

    assert repo.created_tasks == []

def test_ai_plan_subtasks_does_not_touch_difficulty_when_override_disabled():
    task = make_root_task()
    task.difficulty = TaskDifficulty.EASY  # caller-provided value
    repo = FakeRepo(tasks={task.id: task})
    reply = '{"difficulty": "HARD", "should_split": false, "sub_tasks": []}'
    service = make_service(repo, chatbot=FakeChatbot(reply))

    service._ai_plan_subtasks(task, override_difficulty=False)

    assert task.difficulty == TaskDifficulty.EASY  # AI's "HARD" opinion ignored

# ---- AI difficulty-only assessment (used for sub-tasks) ----

def test_ai_assess_difficulty_returns_ai_value():
    service = make_service(FakeRepo(), chatbot=FakeChatbot('{"difficulty": "HARD"}'))

    result = service._ai_assess_difficulty({"title": "t", "context": "c", "estimated_hours_min": 1, "estimated_hours_max": 2})

    assert result == TaskDifficulty.HARD

def test_ai_assess_difficulty_returns_none_on_chatbot_error():
    service = make_service(FakeRepo(), chatbot=FakeChatbot(RuntimeError("down")))

    result = service._ai_assess_difficulty({"title": "t"})

    assert result is None

# ---- create_task: difficulty is optional, AI fills it in when null ----

def test_create_task_fills_null_difficulty_via_ai_for_subtask():
    from domains.task.schemas import TaskCreate

    root = make_task(id=1)
    repo = FakeRepo(tasks={1: root})
    service = make_service(repo, chatbot=FakeChatbot('{"difficulty": "HARD"}'))

    created = service.create_task(TaskCreate(
        title="Sub without difficulty", difficulty=None, company_id=1,
        parent_task_id=1, estimated_hours_min=1, estimated_hours_max=2,
        competency_points=10, context="ctx",
    ))

    assert created.difficulty.value == "HARD"

def test_create_task_root_keeps_explicit_difficulty_despite_ai_opinion():
    from domains.task.schemas import TaskCreate

    repo = FakeRepo()
    reply = '{"difficulty": "HARD", "should_split": false, "sub_tasks": []}'
    service = make_service(repo, chatbot=FakeChatbot(reply))

    created = service.create_task(TaskCreate(
        title="Root with explicit difficulty", difficulty="EASY", company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, competency_points=10, context="ctx",
    ))

    assert created.difficulty.value == "EASY"  # NOT overridden by the AI's "HARD"

def test_create_task_root_uses_ai_difficulty_when_null():
    from domains.task.schemas import TaskCreate

    repo = FakeRepo()
    reply = '{"difficulty": "HARD", "should_split": false, "sub_tasks": []}'
    service = make_service(repo, chatbot=FakeChatbot(reply))

    created = service.create_task(TaskCreate(
        title="Root without difficulty", difficulty=None, company_id=1,
        estimated_hours_min=1, estimated_hours_max=2, competency_points=10, context="ctx",
    ))

    assert created.difficulty.value == "HARD"

# ---- submit_report scoped by (task_id, student_id) ----

def test_submit_report_raises_not_found_when_student_never_joined():
    repo = FakeRepo()
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service.submit_report(task_id=1, student_id=42, report_url="https://example.com/r")

# ---- depth validation ----

def test_validate_parent_rejects_nesting_deeper_than_two_levels():
    sub_task = make_task(id=2, parent_task_id=1)
    repo = FakeRepo(tasks={1: make_task(id=1), 2: sub_task})
    service = make_service(repo)

    with pytest.raises(BusinessLogicException):
        service._validate_parent(2)

def test_validate_parent_allows_root_task_as_parent():
    root = make_task(id=1)
    repo = FakeRepo(tasks={1: root})
    service = make_service(repo)

    service._validate_parent(1)  # should not raise

def test_validate_parent_noop_when_none():
    service = make_service(FakeRepo())
    service._validate_parent(None)  # should not raise

# ---- criteria weight validation ----

def test_validate_criteria_weights_rejects_sum_not_100():
    service = make_service(FakeRepo())
    with pytest.raises(BusinessLogicException):
        service._validate_criteria_weights([{"weight_percent": 60}, {"weight_percent": 30}])

def test_validate_criteria_weights_accepts_sum_100():
    service = make_service(FakeRepo())
    service._validate_criteria_weights([{"weight_percent": 60}, {"weight_percent": 40}])  # should not raise

def test_validate_criteria_weights_noop_when_empty():
    service = make_service(FakeRepo())
    service._validate_criteria_weights([])  # should not raise

# ---- progress rollup ----

def test_progress_sums_points_only_from_completed_sub_task_submissions():
    root = make_task(id=1)
    sub_a = make_task(id=2, parent_task_id=1)
    sub_b = make_task(id=3, parent_task_id=1)
    sub_a.title, sub_b.title = "Sub A", "Sub B"

    repo = FakeRepo(
        tasks={1: root},
        sub_tasks={1: [sub_a, sub_b]},
        submissions={
            (2, 99): SimpleNamespace(status=SubmissionStatus.COMPLETED, points_awarded=20),
            (3, 99): SimpleNamespace(status=SubmissionStatus.SUBMITTED, points_awarded=None),
        },
    )
    service = make_service(repo)

    progress = service.get_task_progress(1, 99)

    assert progress["total_points_awarded"] == 20
    assert progress["is_fully_completed"] is False

def test_progress_is_fully_completed_when_all_sub_tasks_done():
    root = make_task(id=1)
    sub_a = make_task(id=2, parent_task_id=1)
    sub_b = make_task(id=3, parent_task_id=1)
    sub_a.title, sub_b.title = "Sub A", "Sub B"

    repo = FakeRepo(
        tasks={1: root},
        sub_tasks={1: [sub_a, sub_b]},
        submissions={
            (2, 99): SimpleNamespace(status=SubmissionStatus.COMPLETED, points_awarded=20),
            (3, 99): SimpleNamespace(status=SubmissionStatus.COMPLETED, points_awarded=30),
        },
    )
    service = make_service(repo)

    progress = service.get_task_progress(1, 99)

    assert progress["total_points_awarded"] == 50
    assert progress["is_fully_completed"] is True
