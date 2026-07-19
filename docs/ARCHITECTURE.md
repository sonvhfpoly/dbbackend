# Architecture — WORKLAB / Career Guidance Backend

Kiến trúc, design pattern, và bản đồ domain hiện tại. Xem [requirements.md](requirements.md) cho spec sản phẩm (nguồn sự thật cho business rules), [DATA_MODEL.md](DATA_MODEL.md) cho chi tiết entity của `task`/`evidence`/`eportfolio`, và [TESTING.md](TESTING.md) cho hướng dẫn chạy/test.

## 1. Nguyên tắc thiết kế

**Domain-Driven Design + Layered Architecture** (Router → Service → Repository → Model), mỗi domain nằm độc lập dưới `app/domains/`:

```
app/
├── main.py              # Entry point: FastAPI init, include_router mọi domain, import mọi models.py
├── core/
│   ├── config.py        # Pydantic Settings — mọi biến môi trường, có default hợp lý cho dev
│   ├── database.py       # SQLAlchemy engine/session/Base
│   ├── security.py       # bcrypt password hashing (không có JWT/login flow — xem mục 5)
│   └── exceptions.py     # BusinessLogicException, EntityNotFoundException, UnauthorizedException
├── alembic/               # Migration versioned (xem mục 4)
├── domains/
│   ├── market/           # Skill, Career, Job, JobPosting — market data & labor trends
│   ├── student/          # Student, StudentProfile, StudentSkillProfile/Event, CareerRecommendation
│   ├── guidance/         # EducationPath catalog + Task recommendation (target Job) + AntiBiasEngine
│   ├── chatbot/          # Stateless proxy tới LLM chat API (không có models.py)
│   ├── task/             # Company, Task (sub-task), TaskSkill, TaskReview, TaskSubmission, TaskSubmissionFile
│   ├── task_builder/     # AI Task Builder — brief doanh nghiệp → Task có cấu trúc
│   ├── evidence/         # EvidenceClaim — AI draft → student review → mentor verify
│   └── eportfolio/       # Aggregation view (student + business) + share consent
└── tests/unit/            # Pure-logic tests, không cần DB thật (xem TESTING.md)
```

**Wiring rule**: `main.py` là nơi duy nhất biết về mọi domain. Nó phải `include_router()` router của từng domain và import `models.py` của từng domain (kể cả domain chưa có router) để `Base.metadata` thấy đủ bảng trước khi tạo schema. Một domain tồn tại dưới `domains/` nhưng không được import/đăng ký ở đây là dead code.

**Layer responsibility (SRP)**:
- **Router**: nhận HTTP request, validate qua Pydantic schema, gọi Service, trả response. Không chứa business logic.
- **Service**: business logic, state machine transitions, gọi AI client, điều phối giữa các repository (kể cả cross-domain).
- **Repository**: chỉ truy vấn DB (SQLAlchemy Session), không business logic.
- **Model**: định nghĩa schema DB (SQLAlchemy `Mapped`/`mapped_column`).

**Design patterns đang dùng**:
- **Strategy Pattern** (`domains/guidance/anti_bias.py`) — `AntiBiasEngine` chạy list các `BiasValidator` (`DiversityValidator`, `RegionExpansionValidator`), thêm rule mới không sửa code cũ (Open/Closed).
- **Dependency Injection** — DB session và AI client được inject qua FastAPI `Depends`, giúp test thay repo/chatbot giả (`object.__new__(Service)` rồi gán `.repo`/`.chatbot` — xem TESTING.md).
- **Enum re-export** — mỗi domain định nghĩa enum **một lần** trong `models.py`; `schemas.py` import lại (`from .models import X  # noqa: F401`) thay vì định nghĩa trùng, tránh 2 nguồn giá trị lệch nhau.

## 2. Bản đồ domain hiện tại

| Domain | Vai trò | Phụ thuộc cross-domain |
|---|---|---|
| `market` | Skill/Career/Job/JobPosting catalog, market trend, dashboard overview | — |
| `student` | Student profile, skill leveling (`StudentSkillProfile`/`StudentSkillEvent`), LLM career recommendation | `market` (Skill/Career catalog), `task` (completed-task context, không dùng làm skill signal — xem mục 5) |
| `guidance` | EducationPath catalog; gợi ý **Task** tiếp theo hướng tới 1 target Job (không còn gợi ý EducationPath, xem mục 5) | `student` (`StudentSkillProfile`), `market`, `task` |
| `chatbot` | Proxy LLM chat-completions (FPT Cloud hoặc Vertex AI) | — (được `guidance`/`task`/`task_builder`/`student` gọi làm client) |
| `task` | Task marketplace: company task, sub-task, review (T/R-level), submission workflow, `TaskSkill` (skill mỗi task rèn luyện) | `chatbot`, `market` (Skill), `evidence` (auto-draft claim khi hoàn thành — xem mục 5) |
| `task_builder` | AI chat nhiều lượt biến brief doanh nghiệp thành `Task` thật | `task`, `chatbot` |
| `evidence` | EvidenceClaim state machine (tạo thủ công hoặc tự động khi task hoàn thành), cập nhật `StudentSkillProfile` khi mentor verify | `task` (skill snapshot, `TaskSkill`), `market` (Skill), `student` (skill event) |
| `eportfolio` | Tổng hợp view cho student/business, share consent | `student`, `evidence`, `task`, `market` |

## 3. Không có Auth/RBAC — quyết định có chủ đích

MVP này **không có** User/Role/Login/JWT. Mọi `student_id`/`mentor_id`/`reviewer_id`/`company_id` là số nguyên do caller truyền thẳng, không xác thực danh tính. Đây là lựa chọn có chủ đích để tối ưu cho demo/test đơn giản (không cần login flow trước mỗi test, đóng vai actor nào chỉ cần đổi 1 param), **không phải thiếu sót cần vá gấp**. `core/security.py` chỉ còn bcrypt password hashing utility, không có JWT issuance.

Nếu sau này cần thêm auth thật, đó là một quyết định mới cần cân nhắc lại toàn bộ Role & Permission Matrix ở [requirements.md §5](requirements.md#5-role--permission-matrix), không phải một việc bật lại "phase đã hoãn".

## 4. Schema & Migration (Alembic)

Schema được version hóa bằng Alembic, nằm ở `app/alembic/` (cấu hình `app/alembic.ini`). `env.py` đọc `DATABASE_URL` từ `core.config.settings` (không hardcode), và import mọi domain's `models.py` để `target_metadata` thấy đủ bảng.

- **Production/staging**: `alembic upgrade head` là cách DUY NHẤT được phép đổi schema.
- **Dev/demo convenience**: `AUTO_CREATE_SCHEMA=true` (mặc định) — `Base.metadata.create_all()` chạy ở `main.py` lúc startup, tự tạo bảng còn thiếu, không cần chạy `alembic upgrade head` tay trước mỗi lần thử. Đây chỉ additive (không alter/drop), nên không làm schema trôi dạt — set `false` ở môi trường chia sẻ/production.

Xem [TESTING.md § Alembic](TESTING.md#alembic--migration) để biết cách tạo migration mới và cách stamp một DB đã có sẵn schema từ `create_all()` cũ.

## 5. Ghi chú tích hợp cross-domain

- **`task` ↔ `evidence`**: `EvidenceClaim.task_complexity`/`.risk_level` là **snapshot** tại thời điểm tạo claim (không FK-follow sống), để một thay đổi sau này trên `Task` không viết lại ngầm bối cảnh mà evidence đã được tạo ra.
- **`task` → `evidence` (tự động)**: `TaskService._ai_link_skills` (AI, lúc tạo task) và `set_task_skills` (thủ công) ghi vào `TaskSkill` — task nào rèn skill nào. Khi 1 submission hoàn thành (`complete_submission`, `mentor_review` approve, hoặc `run_auto_check` khi không cần mentor — cả 3 nơi), `TaskService._draft_evidence_for_completion` đọc lại `TaskSkill` và tự tạo 1 `EvidenceClaim` (`AI_DRAFT`) cho mỗi skill, dùng `Task.target_evidence_level` làm `proposed_skill_level`. Claim vẫn phải đi hết state machine (`AI_DRAFT → ... → VERIFIED`) — không có đường tắt tự-verify.
- **`evidence` → `student`**: khi mentor quyết định `VERIFIED`, `EvidenceService._apply_to_skill_profile` gọi thẳng `StudentProfileService.create_student_skill_event(...)` (không qua HTTP, gọi Python trực tiếp trong cùng process) — đây là **điểm human-in-the-loop duy nhất** cập nhật skill level (xem [requirements.md §29](requirements.md#29-ai-traceability)).
- **`StudentSkillProfile` là nguồn "known skill" DUY NHẤT** cho mọi service cần biết "student giỏi gì": `guidance` (Task recommendation), `eportfolio` (`verified_skills`), và `student` chính nó (`generate_student_career_recommendations`). Bảng `StudentSkill` (tag nhị phân cũ) đã bị xóa hoàn toàn. Riêng `student`'s career recommendation đọc thêm `Task`/`TaskSubmission` để lấy **ngữ cảnh** (tiêu đề/điểm/feedback task đã hoàn thành cho LLM viết rationale) — nhưng tín hiệu skill thật sự đưa vào prompt luôn chỉ lấy từ `StudentSkillProfile`, không bao giờ từ `Task.skills`.
- **`task_builder` → `task`**: `TaskBuilderService.generate_task` gọi `TaskService.create_task(..., skip_ai_planning=False)` thay vì tạo thẳng qua `TaskRepository` — nghĩa là task sinh ra từ AI Task Builder đi qua đúng 1 pipeline tạo task duy nhất, **kể cả bước AI tự tách sub-task** (`_ai_plan_subtasks`) nếu phiên bản đã chọn qua hội thoại vẫn quá rộng cho 1 lần nộp. `complexity_level` đã chốt qua hội thoại không bị AI planning ghi đè (`create_task` truyền `override_complexity=False` bất cứ khi nào `complexity_level` đã được set sẵn). Đồng thời copy mọi `TBDocument` (tài liệu doanh nghiệp đính kèm lúc chat) sang `TaskInput` của task vừa tạo (`input_type=DOCUMENT`, kèm `storage_url`) — client (business/mentor/student) đọc file gốc qua `TaskRead.inputs`, không cần quay lại API `task-builder/conversations/{id}` nữa.
- **`company_id` không bao giờ hard-fail**: `TaskService.resolve_company_id` được gọi từ cả `create_task` và `TaskBuilderService.start_conversation` — bỏ trống hoặc trỏ tới company không tồn tại đều tự resolve về 1 `Company` placeholder dùng chung (tạo lười lần đầu cần tới, matched theo slug), thay vì để lộ `IntegrityError`/`500` do vi phạm FK. Xem [DATA_MODEL.md](DATA_MODEL.md#task--catalog-nhiệm-vụ).
- **`task` → `evidence` khi xóa**: `TaskService.delete_task` luôn từ chối xóa (dù có `force=true`) nếu task (hoặc sub-task của nó) còn `EvidenceClaim` tham chiếu — evidence có thể đã cập nhật `StudentSkillProfile` ở domain `student`, và việc xóa task không có cách nào an toàn để undo tác dụng phụ đó. Sub-task/`TaskSubmission` thì cascade được khi `force=true`. Xem [DATA_MODEL.md § Xóa Task](DATA_MODEL.md#xóa-task-delete-taskstask_id).
- **`eportfolio`** không có model nghiệp vụ riêng ngoài `PortfolioShareSetting` — mọi field khác được tổng hợp real-time từ `student`/`evidence`/`task`/`market` mỗi lần gọi, không đồng bộ/cache riêng.

## 6. Ràng buộc đạo đức (bắt buộc với domain `guidance`)

Mọi đề xuất phải mở rộng lựa chọn thay vì đóng khung người dùng, không củng cố định kiến giới/vùng miền, và phải kèm `reasoning_explanation` để học sinh/sinh viên tự quyết định dựa trên tham khảo — không phải chỉ định. Xem `AntiBiasEngine` (Strategy Pattern) trong `domains/guidance/anti_bias.py`.
