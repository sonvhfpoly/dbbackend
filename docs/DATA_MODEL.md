# Data Model — Task, Evidence, ePortfolio

Data model thật (đã implement) của 3 domain lõi trong luồng "AI proposes → Human reviews → System records → Student owns evidence" ([requirements.md §40](requirements.md#40-nguyên-tắc-chung-cho-3-team)): `task`, `evidence`, `eportfolio`. Xem [ARCHITECTURE.md](ARCHITECTURE.md) cho bức tranh toàn bộ 8 domain, [MARKET_DATA_MODEL.md](MARKET_DATA_MODEL.md) cho `market`/`student`.

Quyết định thiết kế nền tảng (áp dụng cho cả 3 domain):

- **Không có Auth** — mọi `student_id`/`reviewer_id`/`mentor_id`/`company_id` là **tham chiếu lỏng** (plain `int`, không FK) tới một identity không tồn tại trong hệ thống này. Xem [ARCHITECTURE.md §3](ARCHITECTURE.md#3-không-có-authrbac--quyết-định-có-chủ-đích).
- **State machine được model tường minh**, validate ở service layer (không phải DB constraint) — mọi transition sai trả `400` kèm lý do rõ ràng.
- **Snapshot thay vì live-read** ở bất kỳ đâu lịch sử cần bất biến: `TaskSubmission.points_awarded`, `EvidenceClaim.task_complexity`/`.risk_level` — một thay đổi sau này trên `Task` không viết lại ngầm dữ liệu lịch sử.

---

## 1. Domain `task`

### `Company`
Doanh nghiệp tài trợ task. `slug` unique dùng cho route URL-friendly. `is_verified` để UI cân nhắc ẩn/gắn nhãn cảnh báo task từ công ty chưa xác minh (business rule, không phải DB constraint).

### `Task` — catalog nhiệm vụ

| field | type | ghi chú |
|---|---|---|
| id | PK | |
| title | str(255) | |
| company_id | FK → `Company.id` | |
| parent_task_id | Optional[int], FK → `Task.id`, self-ref | null = task gốc; có giá trị = sub-task. Task được trỏ tới **không được** có `parent_task_id` khác null — tối đa 2 cấp, validate ở service |
| sort_order | int, default 0 | thứ tự sub-task cùng cha |
| estimated_hours_min/max | int | |
| competency_points | int, nullable | bắt buộc khi là leaf task; null khi có sub-task (điểm cộng dồn — xem `get_task_progress`) |
| context | str(4000) | |
| scope_included / scope_excluded | JSON list[str] | |
| requires_auto_check / requires_mentor_approval | bool | |
| mentor_approval_sla_hours | int, nullable | |
| data_privacy_notice | str, nullable | |
| **checkpoints** | JSON list[str] | milestone hiển thị cho student — display-only, không có backend gate nào gắn vào |
| **complexity_level** | enum `TaskComplexity` (T1/T2/T3) | T-level — nguồn sự thật DUY NHẤT cho "task khó cỡ nào" (field `difficulty` EASY/MEDIUM/HARD cũ đã bị gỡ bỏ hoàn toàn, xem ghi chú bên dưới) |
| **risk_level** | enum `TaskRiskLevel` (R0/R1/R2/R3) | R-level; R2/R3 tồn tại trong enum (không như T4/T5 bị loại khỏi `TaskComplexity`) vì rule chặn là runtime gate, không phải giới hạn kiểu dữ liệu |
| **target_evidence_level** | enum `EvidenceLevel` (L1-L5) | mức skill task này nhắm tới tạo evidence |
| **review_status** | enum `TaskReviewStatus` | `PENDING_MENTOR_APPROVAL` (default) → `APPROVED`/`REJECTED`/`NEED_MORE_INFO`. Task chỉ join được khi `APPROVED` |
| created_at | datetime | |

> **Về việc gộp `difficulty` → `complexity_level`**: bản đầu tiên của domain `task` (trước khi map theo `requirements.md`) có field `difficulty` (EASY/MEDIUM/HARD) độc lập với T-level. Hai field mô tả cùng một khái niệm nên đã được gộp — `complexity_level` (T1-T3) là field duy nhất còn lại, dùng cho cả AI auto-assess lẫn mentor override. Đừng tái tạo lại field `difficulty`.

> **Về `company_id` bỏ trống/không hợp lệ**: `TaskCreate.company_id` (và `TBConversationCreate.company_id`) là `Optional[int]` ở tầng request. Nếu bỏ trống hoặc trỏ tới một `company_id` không tồn tại, `TaskService.resolve_company_id` tự resolve về một `Company` placeholder dùng chung (`slug="unregistered-company"`, tạo lười lần đầu cần tới) thay vì raise lỗi — cột DB vẫn `NOT NULL` FK như bảng trên, mọi `Task`/`TBConversation` luôn trỏ tới một company thật, chỉ có thể là placeholder thay vì company caller định nhắc tới. Gọi từ cả `TaskService.create_task` lẫn `TaskBuilderService.start_conversation`.

### `TaskReview` — quyết định của mentor trên chính Task (khác `TaskSubmission` review)

Append-only history (1 task có thể được review nhiều lần: `NEED_MORE_INFO` → business sửa → review lại). `Task.review_status` luôn phản ánh quyết định gần nhất.

| field | type | ghi chú |
|---|---|---|
| id | PK | |
| task_id | FK → `Task.id` | |
| reviewer_id | int, không FK | mentor thực hiện quyết định |
| decision | enum `TaskReviewStatus` | phải là `APPROVED`/`REJECTED`/`NEED_MORE_INFO` — không bao giờ là `PENDING_MENTOR_APPROVAL` |
| approved_complexity/risk/evidence_level | Optional enum | override giá trị đề xuất; nếu có, ghi đè `Task.complexity_level`/`.risk_level`/`.target_evidence_level` tương ứng |
| comment | str, nullable | |
| created_at | datetime | |

**Business rule bắt buộc** ([requirements.md §4.2](requirements.md#42-task-risk--r-level)): `IF risk_level >= R2 THEN task cannot transition to APPROVED` — enforce ở `TaskService.review_task`, có unit test riêng (`test_task_review.py`).

### `TaskInput` / `TaskOutput` / `TaskEvaluationCriterion`
Bảng con 1-N của `Task` — input tài liệu/dataset, output mong đợi, tiêu chí đánh giá (`weight_percent` phải tổng = 100%/task, validate ở service).

### `TaskSubmission` — tiến trình 1 student trên 1 Task

| field | type | ghi chú |
|---|---|---|
| id | PK | |
| task_id | FK → `Task.id` | |
| student_id | int, không FK | Student ở domain khác, tham chiếu lỏng |
| status | enum `SubmissionStatus` | state machine bên dưới |
| joined_at | datetime | đồng thời đóng vai "`accepted_at`" của MVP ([requirements.md §12](requirements.md#12-task-time-tracking)) — không có bước assign→accept riêng, join = accept |
| report_url | str, nullable | link báo cáo |
| submitted_at | datetime, nullable | |
| **elapsed_seconds** | int, nullable | `submitted_at - joined_at`. **Chỉ hiển thị dạng "N ngày M giờ", không bao giờ dùng làm Skill Signal** ([requirements.md §12](requirements.md#constraint)) |
| **student_reflection** | JSON, nullable | `{challenge, ai_usage, changes_after_feedback, remaining_uncertainty[]}` ([requirements.md §15](requirements.md#15-submission-requirements)) — form tự do vì bộ câu hỏi "Configurable" theo spec |
| auto_check_result | JSON, nullable | bị xóa (`null`) mỗi lần student nộp lại — xem ghi chú resubmit bên dưới |
| mentor_feedback | str, nullable | bị xóa (`null`) mỗi lần student nộp lại — xem ghi chú resubmit bên dưới |
| mentor_decision_at | datetime, nullable | bị xóa (`null`) mỗi lần student nộp lại — xem ghi chú resubmit bên dưới |
| completed_by | enum `CompletionActor` (AI/MENTOR), nullable | |
| points_awarded | int, nullable | **snapshot** `Task.competency_points` tại thời điểm hoàn thành |
| completed_at | datetime, nullable | |

**State machine** (`SubmissionStatus`):
```
JOINED → SUBMITTED → AUTO_CHECK_PASSED ─┐
                    └→ AUTO_CHECK_FAILED  (quay lại SUBMITTED)
                                          ├→ MENTOR_APPROVED → COMPLETED
                                          └→ MENTOR_REJECTED  (quay lại SUBMITTED)
```
Nếu `Task.requires_mentor_approval=false`, có thể đi thẳng `AUTO_CHECK_PASSED → COMPLETED` với `completed_by=AI`.

> **Về resubmit sau `MENTOR_REJECTED`/`AUTO_CHECK_FAILED`**: `TaskService.submit_report` cho phép nộp lại (đúng theo `requirements.md`'s Revision Flow, được gộp đơn giản vào lại `MENTOR_REJECTED`/`SUBMITTED` thay vì thêm state `REVISION_REQUESTED`/`RESUBMITTED_TO_MENTOR` riêng). Mỗi lần nộp lại, `mentor_feedback`/`mentor_decision_at`/`auto_check_result` của vòng review trước bị xóa về `null` — nếu không, bản nộp mới (chưa ai xem) sẽ trông như đã có quyết định từ vòng cũ, dễ khiến client tưởng nhầm trạng thái và gọi `/submit` lần nữa trong khi `status` thật đã tiến lên `SUBMITTED`.

### `TaskSubmissionFile` — metadata file đã upload ([requirements.md §14](requirements.md#14-file-upload-requirements))

| field | type | ghi chú |
|---|---|---|
| id | PK | |
| submission_id | FK → `TaskSubmission.id` | |
| file_name / mime_type / size_bytes / file_url | | |
| scan_status | enum `FileScanStatus` (PENDING/PASSED/FAILED) | placeholder — chưa tích hợp virus scanner thật, đăng ký file tự động `PASSED` |
| uploaded_at | datetime | |

Giới hạn MVP: **max 50MB/file** (validate ở schema `RegisterSubmissionFileRequest`), **max 10 file/submission** (validate ở `TaskService.register_submission_file`).

### `TaskSubmissionScore` — điểm chấm theo từng tiêu chí
Khác `TaskEvaluationCriterion` (rubric tĩnh) — bảng này lưu kết quả chấm thật cho 1 submission cụ thể. Upsert theo `(submission_id, criterion_id)`.

### ERD tóm tắt
```
Company (1) ──< (N) Task
Task    (1) ──< (N) TaskInput / TaskOutput / TaskEvaluationCriterion / TaskReview / TaskSubmission
Task    (1) ──< (N) Task                     (self-ref parent_task_id, tối đa 2 cấp)
TaskSubmission (1) ──< (N) TaskSubmissionScore / TaskSubmissionFile
TaskSubmission.student_id ─ ─ ─ (tham chiếu lỏng) ─ ─ ─> Student (domain khác)
```

### Xóa Task (`DELETE /tasks/{task_id}`)

`TaskInput`/`TaskOutput`/`TaskEvaluationCriterion`/`TaskReview` cascade tự động (`cascade="all, delete-orphan"` trên relationship của `Task`). Sub-task và `TaskSubmission` thì không — `TaskService.delete_task`:

- **Có `EvidenceClaim` tham chiếu tới task (hoặc bất kỳ sub-task nào)**: luôn bị chặn (`400`), **kể cả khi `force=true`** — evidence đã có thể cập nhật `StudentSkillProfile` ở nơi khác ([EvidenceService._apply_to_skill_profile](#2-domain-evidence)), xóa task không có cách nào an toàn để undo việc đó.
- **Có sub-task hoặc `TaskSubmission`, không có evidence**: mặc định chặn (`400`); truyền `?force=true` để cascade xóa sub-task (kèm submission/review của chính nó) rồi tới task cha, theo đúng thứ tự con-trước-cha (tránh vi phạm FK `parent_task_id`).
- Không có gì phụ thuộc: xóa ngay, trả `204`.

---

## 2. Domain `evidence`

### `EvidenceClaim` ([requirements.md §20](requirements.md#20-evidence-requirements))

| field | type | ghi chú |
|---|---|---|
| id | PK | |
| student_id | int, không FK | |
| skill_id | FK → `Skill.id` (domain `market`) | |
| task_id | FK → `Task.id` | |
| claim | str(2000) | |
| observed_actions | JSON list[str] | |
| evidence_sources | JSON list[str] | giá trị hợp lệ: `FINAL_OUTPUT`, `STUDENT_REFLECTION`, `AI_MENTOR_INTERACTION`, `MENTOR_REVIEW` |
| task_complexity / risk_level | str | **snapshot** T-level/R-level của Task tại thời điểm tạo claim — không FK-follow sống |
| autonomy_level | enum `AutonomyLevel` (GUIDED/SEMI_INDEPENDENT/INDEPENDENT) | |
| proposed_skill_level | str | "L1".."L5" |
| status | enum `EvidenceStatus` | state machine bên dưới |
| mentor_id | int, không FK, nullable | |
| mentor_comment | str, nullable | |
| created_at / decided_at | datetime | |

**State machine** (`EvidenceStatus`):
```
AI_DRAFT → STUDENT_REVIEWED → PENDING_MENTOR → VERIFIED
                                             ├→ NEED_MORE_EVIDENCE
                                             └→ REJECTED
```

**Điểm human-in-the-loop quan trọng nhất hệ thống**: chỉ khi mentor quyết định `VERIFIED`, `EvidenceService._apply_to_skill_profile` mới gọi `StudentProfileService.create_student_skill_event(...)` (domain `student`) để thực sự đổi `StudentSkillProfile.level`. `REJECTED`/`NEED_MORE_EVIDENCE` **không** đụng vào skill profile. Việc này khớp đúng nguyên tắc `AI proposes Evidence → Mentor verifies` ([requirements.md §29](requirements.md#29-ai-traceability)).

---

## 3. Domain `eportfolio`

Không có model nghiệp vụ riêng — mọi field trong response là **tổng hợp real-time** (không cache) từ `student`/`evidence`/`task`/`market` mỗi lần gọi API. Model duy nhất:

### `PortfolioShareSetting`

| field | type | ghi chú |
|---|---|---|
| id | PK | |
| student_id | FK → `Student.id`, unique | 1 dòng/student |
| share_with_business | bool, default False | consent bắt buộc trước khi business xem được business-view ([requirements.md §21](requirements.md#21-eportfolio-requirements)) |
| updated_at | datetime | |

Business view (`GET /eportfolio/students/{id}/business-view`) trả `403` nếu chưa có consent — không có dữ liệu nào rò rỉ ra ngoài khi `share_with_business=False`.

---

## 4. Enum tổng hợp

| Domain | Enum | Giá trị |
|---|---|---|
| task | `TaskComplexity` | T1, T2, T3 |
| task | `TaskRiskLevel` | R0, R1, R2, R3 |
| task | `EvidenceLevel` | L1, L2, L3, L4, L5 |
| task | `TaskReviewStatus` | PENDING_MENTOR_APPROVAL, APPROVED, REJECTED, NEED_MORE_INFO |
| task | `SubmissionStatus` | JOINED, SUBMITTED, AUTO_CHECK_PASSED, AUTO_CHECK_FAILED, MENTOR_APPROVED, MENTOR_REJECTED, COMPLETED |
| task | `CompletionActor` | AI, MENTOR |
| task | `TaskInputType` | DATASET, DOCUMENT, OTHER |
| task | `FileScanStatus` | PENDING, PASSED, FAILED |
| evidence | `EvidenceStatus` | AI_DRAFT, STUDENT_REVIEWED, PENDING_MENTOR, VERIFIED, NEED_MORE_EVIDENCE, REJECTED |
| evidence | `EvidenceSource` | FINAL_OUTPUT, STUDENT_REFLECTION, AI_MENTOR_INTERACTION, MENTOR_REVIEW |
| evidence | `AutonomyLevel` | GUIDED, SEMI_INDEPENDENT, INDEPENDENT |

Mỗi enum chỉ định nghĩa **một lần** trong `models.py` của domain đó — `schemas.py` re-export (`from .models import X`), không định nghĩa trùng (xem [ARCHITECTURE.md §1](ARCHITECTURE.md#1-nguyên-tắc-thiết-kế)).

## 5. Giả định còn mở

- **Không có entity Mentor/User** — `reviewer_id`/`mentor_id` chỉ là số nguyên, chưa gắn identity thật. Nếu cần audit theo từng mentor cụ thể, cần thêm domain identity (xem [ARCHITECTURE.md §3](ARCHITECTURE.md#3-không-có-authrbac--quyết-định-có-chủ-đích) — quyết định có chủ đích, chưa lên kế hoạch làm).
- **Không có Team/nhóm** — `requirements.md` §2.2/§5 nhắc tới "tạo nhóm" nhưng chưa có `Team`/`TeamMember` entity nào trong codebase hiện tại.
- **Không có Notification/AuditLog/ActivityEvent** — `requirements.md` §17/§18/§26 mô tả các entity này nhưng chưa implement.
