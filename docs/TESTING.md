# Testing & Integration Guide

Hướng dẫn chạy, test, và tích hợp toàn bộ 8 domain hiện có. Xem [ARCHITECTURE.md](ARCHITECTURE.md) cho bức tranh domain, [DATA_MODEL.md](DATA_MODEL.md)/[MARKET_DATA_MODEL.md](MARKET_DATA_MODEL.md) cho chi tiết entity, [requirements.md](requirements.md) cho spec gốc.

## 0. Chuẩn bị

```bash
cd app
uv run --project .. uvicorn main:app --reload --port 8000
```

Mở Swagger UI: http://127.0.0.1:8000/docs — mọi bước dưới đây làm được qua "Try it out" hoặc `curl` như liệt kê. Đảm bảo `app/.env` có `DATABASE_URL` (bắt buộc); `FPT_CLOUD_API_KEY` hoặc Vertex AI ADC bắt buộc riêng cho các bước gọi AI thật (`guidance`, `task` auto-planning, `task_builder`, `chatbot`).

Không cần chạy `alembic upgrade head` trước — `AUTO_CREATE_SCHEMA=true` (mặc định) tự tạo bảng còn thiếu lúc server khởi động. Xem [§8](#8-alembic--migration) nếu cần biết cách quản lý migration thật.

## 1. Chạy test tự động (pytest, không cần DB/AI thật)

```bash
uv run --project .. pytest -q
```

146 test hiện có, chia theo file:

| File | Domain | Nội dung |
|---|---|---|
| `unit/test_market_service.py` | market | Ingestion, trend calculation, skill/job resolution |
| `unit/test_anti_bias.py` | guidance | `DiversityValidator`/`RegionExpansionValidator` |
| `unit/test_task_service.py` | task | AI complexity/sub-task planning, nesting depth, progress rollup, `skip_ai_planning` |
| `unit/test_task_review.py` | task | Risk-level gate (R2/R3 chặn APPROVED), `join_task` yêu cầu `APPROVED` |
| `unit/test_task_submission_extras.py` | task | `elapsed_seconds`, `student_reflection`, giới hạn file upload |
| `unit/test_task_builder_service.py` | task_builder | AI turn parsing, giới hạn 3 câu hỏi, `confirm`, `generate_task` (qua `TaskService.create_task(skip_ai_planning=False)`, có thể tự tách sub-task) |
| `unit/test_evidence_service.py` | evidence | State machine `AI_DRAFT→...→VERIFIED`, cập nhật skill profile chỉ khi `VERIFIED` |
| `integration/test_task_review_integration.py` | task | Duyệt task gốc lan truyền `review_status` xuống sub-task (mock DB, SQLite in-memory) |
| `integration/test_task_skill_evidence.py` | task, evidence | `TaskSkill` auto-link lúc tạo task (AI), auto-draft `EvidenceClaim` lúc hoàn thành submission (`_draft_evidence_for_completion`), best-effort khi AI/skill lỗi |
| `integration/test_guidance_task_recommendation.py` | guidance | Gợi ý Task tiếp theo theo target Job — so khớp `StudentSkillProfile` vs `JobSkill`, fallback LLM khi cold-start |
| `integration/test_student_career_recommendations.py` | student | Career recommendation chỉ tin `StudentSkillProfile` (evidence đã `VERIFIED`) làm skill signal, từ chối khi có task hoàn thành nhưng chưa skill nào được xác thực; background refresh sau khi submission `COMPLETED` |

Test `unit/*` dùng pattern bypass DB session: `object.__new__(Service)` rồi gán `.repo`/`.chatbot` là fake object — test logic thuần, không cần DB thật. Test `integration/*` dùng SQLite in-memory thật (`create_engine("sqlite:///:memory:")` + `Base.metadata.create_all()`) khi logic trải dài nhiều domain/repository thật (task↔evidence↔student). Xem code các file trên để viết test tương tự cho domain mới.

## 2. Market + Guidance (end-to-end)

**Thứ tự bắt buộc**: seed `market` trước `guidance` — `guidance` đọc `Career.market_trend` để build prompt AI.

```bash
curl -X POST http://127.0.0.1:8000/market/seed-demo-data
curl -X POST http://127.0.0.1:8000/guidance/seed-demo-data
```

Kiểm tra market:
```bash
curl http://127.0.0.1:8000/market/careers/           # market_trend không phải toàn STABLE
curl "http://127.0.0.1:8000/market/overview?days=30"  # stat card, chart tuần, phân bố khu vực
curl "http://127.0.0.1:8000/market/analytics/skill-trend?window_days=30"
```

Sinh đề xuất — gợi ý **Task tiếp theo** hướng tới 1 target Job (không còn gợi ý `EducationPath`, xem [ARCHITECTURE.md §2](ARCHITECTURE.md#2-bản-đồ-domain-hiện-tại)). Cần `target_job_id` thật (bắt buộc, không có default) — lấy từ `GET /market/jobs/`, và `demo_student_id` từ response seed guidance:
```bash
JOB_ID=<lấy từ GET /market/jobs/>
curl -X POST "http://127.0.0.1:8000/guidance/students/<demo_student_id>/recommendations?target_job_id=$JOB_ID&count=3"
```

**Kỳ vọng**: response là `List[TaskRecommendationRead]` (`task_id`, `title`, `complexity_level`, `target_evidence_level`, `competency_points`, `company_id`, `reasoning_explanation`) — **không** có `id`/`path_id`/`created_at` (không persist, gọi lại bất cứ lúc nào để có gợi ý mới). Mỗi item có `reasoning_explanation` không rỗng. Sinh viên demo (seed qua evidence chain thật — xem [DATA_MODEL.md](DATA_MODEL.md#studentskillprofile-là-nguồn-known-skill-duy-nhất)) chưa có `StudentSkillProfile` khớp job nào sẽ rơi vào nhánh fallback LLM (cold-start).

`GET /guidance/students/{id}/recommendations` (không đổi shape, vẫn `List[RecommendationRead]`/`EducationPath`) giờ chỉ còn tính lịch sử — vì POST ở trên không còn persist, endpoint này sẽ không bao giờ thấy dữ liệu mới sau thay đổi này.

### Checklist
- [ ] `market_trend` của ít nhất 1 career/job khác `STABLE`
- [ ] `skill-trend` có ít nhất 1 skill với `growth_rate` khác `null`
- [ ] Thiếu `target_job_id` ở POST recommendations → `422`
- [ ] Mỗi recommendation có `reasoning_explanation`, task trả về đang `review_status=APPROVED` và học sinh chưa từng `join`
- [ ] `pytest app/tests/unit/test_anti_bias.py app/tests/unit/test_market_service.py app/tests/integration/test_guidance_task_recommendation.py` pass

## 3. Task Marketplace + Task Review

### 3.1. Seed & duyệt task

```bash
curl -X POST http://127.0.0.1:8000/tasks/seed-demo-data
```
Tạo 1 `Company`, 1 task gốc (2 sub-task 20đ/30đ) — **đã tự động `review_status=APPROVED`** (seed data bỏ qua bước duyệt để demo nhanh). Với task tạo thủ công, `review_status` mặc định là `PENDING_MENTOR_APPROVAL` — **phải duyệt trước khi student join được**:

```bash
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Task moi","company_id":1,"estimated_hours_min":1,"estimated_hours_max":2,"competency_points":10,"context":"ctx","complexity_level":"T1","skip_ai_planning":true}'
# -> join ngay sẽ bị 400: "Task ... is not open to students yet (review_status=PENDING_MENTOR_APPROVAL)"

curl -X POST http://127.0.0.1:8000/tasks/<task_id>/review \
  -H "Content-Type: application/json" -d '{"reviewer_id":1,"decision":"APPROVED"}'
# -> giờ mới join được
```

**`skip_ai_planning: true`** bỏ qua lệnh gọi LLM đánh giá T-level/tách sub-task — dùng khi demo/test không muốn phụ thuộc AI provider. Bỏ trống `complexity_level` (và không set `skip_ai_planning`) thì service tự gọi chatbot đánh giá T1/T2/T3.

**`company_id` không bắt buộc**: bỏ trống hoặc truyền một id không tồn tại đều không lỗi — `TaskService.resolve_company_id` tự resolve về company placeholder dùng chung (`GET /tasks/companies/` sẽ thấy `"Unregistered Company"` / slug `unregistered-company` xuất hiện sau lần đầu tiên cần tới):
```bash
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Task khong ro cong ty","estimated_hours_min":1,"estimated_hours_max":2,"competency_points":10,"context":"ctx","complexity_level":"T1","skip_ai_planning":true}'
# -> 200, company_id trong response trỏ tới company placeholder, không phải lỗi
```

**`created_at`/`updated_at`/`deadline`**: `GET /tasks/` giờ trả về `created_at` (tự sinh lúc tạo), `updated_at` (tự cập nhật mỗi lần task bị sửa — mentor review, AI planning), và `deadline` (optional, hạn mong muốn của doanh nghiệp, truyền vào lúc tạo qua `POST /tasks/` hoặc do AI Task Builder tự trích xuất từ brief). `GET /tasks/` mặc định sắp theo `created_at` giảm dần (task mới nhất lên đầu) — không cần FE tự sort theo `id` nữa.

**Risk gate** ([requirements.md §4.2](requirements.md#42-task-risk--r-level)):
```bash
curl -X POST http://127.0.0.1:8000/tasks/<task_id>/review \
  -H "Content-Type: application/json" -d '{"reviewer_id":1,"decision":"APPROVED","approved_risk":"R2"}'
# -> 400: "... has risk_level R2; tasks at R2/R3 cannot be approved in MVP (no Expert Reviewer)"
```

`GET /tasks/pending-approval` liệt kê task đang chờ duyệt — dùng cho "Approval Queue" của mentor ([requirements.md MEN-05](requirements.md#8-functional-requirements--mentor)).

### 3.2. Luồng nộp bài đầy đủ (auto-check only)

```bash
STUDENT=1001
SUB1_ID=<lấy từ GET /tasks/1, field sub_tasks[0].id>

curl -X POST http://127.0.0.1:8000/tasks/$SUB1_ID/join -d "{\"student_id\": $STUDENT}"
curl -X POST http://127.0.0.1:8000/tasks/$SUB1_ID/submit \
  -H "Content-Type: application/json" \
  -d "{\"student_id\": $STUDENT, \"report_url\": \"https://example.com/r.csv\", \"student_reflection\": {\"challenge\":\"du lieu bi thieu\",\"ai_usage\":\"dung AI de goi y cach lam sach\"}}"
```

**Kỳ vọng response `submit`**: `elapsed_seconds` có giá trị (tính từ `joined_at`), `student_reflection` khớp đúng đã gửi.

File, 2 cách (cả 2 cùng giới hạn max 10 file/submission, max 50MB/file — [requirements.md §14](requirements.md#14-file-upload-requirements)):

**(a) Metadata-only** — binary tự lo ở pipeline upload riêng, chỉ đăng ký `file_url` đã có sẵn:
```bash
SUB1_SUBMISSION_ID=<id trả về ở bước join>
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID/files \
  -H "Content-Type: application/json" \
  -d '{"file_name":"report.csv","mime_type":"text/csv","size_bytes":204800,"file_url":"https://storage.example.com/report.csv"}'
```
**Kỳ vọng**: đăng ký file thứ 11 cho cùng submission → `400` ("already has the maximum of 10 files"); `size_bytes` > 50MB (caller tự khai) → `422`.

**(b) Upload thật** — backend nhận binary, tự lưu lên GCS (`SUBMISSION_FILES_GCS_BUCKET`, cần set trước, xem `core/config.py`), trả `file_url` public dạng `https://storage.googleapis.com/...`:
```bash
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID/files/upload \
  -F "file=@/path/to/report.csv;type=text/csv"
```
**Kỳ vọng**: `file_url` mở được ngay trên browser/`curl` khác, không cần auth (public bucket-IAM, xem `TaskSubmissionFile` ở [DATA_MODEL.md](DATA_MODEL.md)); file > 50MB thật (không phải số caller khai) → `413`.

```bash
curl http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID/files
curl http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID
```
**Kỳ vọng**: cả 2 endpoint đều thấy file vừa đăng ký — endpoint sau (`GET .../submissions/{id}`) nhúng sẵn field `files` giống hệt, không cần gọi thêm endpoint riêng (đáp ứng BUS-11 "Files + review", MEN-13 "Fetch files").

Auto-check + complete:
```bash
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID/auto-check
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID/complete -d '{"completed_by": "AI"}'
```

### 3.3. Luồng mentor-review + chấm điểm (sub-task 2)

Xem field `criteria[].id` từ `GET /tasks/{sub2_id}`, rồi:
```bash
curl -X POST http://127.0.0.1:8000/tasks/$SUB2_ID/join -d "{\"student_id\": $STUDENT}"
curl -X POST http://127.0.0.1:8000/tasks/$SUB2_ID/submit -d "{\"student_id\": $STUDENT, \"report_url\": \"https://example.com/r2.pdf\"}"
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB2_SUBMISSION_ID/mentor-review -d '{"approved": true, "feedback": "Tot"}'
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB2_SUBMISSION_ID/scores -d '{"criterion_id": <id>, "score_percent": 90, "scored_by": "MENTOR"}'
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB2_SUBMISSION_ID/complete -d '{"completed_by": "MENTOR"}'
```

### 3.4. Cộng dồn điểm ở task cha

```bash
curl "http://127.0.0.1:8000/tasks/1/progress?student_id=$STUDENT"
```
**Kỳ vọng** sau khi cả 2 sub-task `COMPLETED`: `total_points_awarded: 50`, `is_fully_completed: true`.

### 3.5. Xóa task (`DELETE /tasks/{task_id}`)

```bash
# Task rỗng (không sub-task/submission/evidence) — xóa ngay
curl -X DELETE http://127.0.0.1:8000/tasks/<task_id_khong_lien_quan>
# -> 204

# Task gốc có sub-task/submission, chưa force -> bị chặn
curl -X DELETE http://127.0.0.1:8000/tasks/1
# -> 400: "... has N sub-task(s) and M submission(s); pass force=true ..."

curl -X DELETE "http://127.0.0.1:8000/tasks/1?force=true"
# -> 204, sub-task + submission (kèm scores/files) bị xóa theo, xóa con trước cha

# Có evidence claim tham chiếu tới task này -> luôn bị chặn, kể cả force=true
curl -X DELETE "http://127.0.0.1:8000/tasks/<task_co_evidence>?force=true"
# -> 400: "... has N evidence claim(s) recorded against it — deleting a task never cascades into evidence records."
```

### Checklist
- [ ] Task mới tạo (không seed) có `review_status: PENDING_MENTOR_APPROVAL`, `join` bị chặn cho tới khi `review` với `decision: APPROVED`
- [ ] `approved_risk: R2`/`R3` luôn bị chặn khi `decision: APPROVED`, dù risk gốc của task là gì
- [ ] `submit` trả `elapsed_seconds` hợp lệ và đúng `student_reflection` đã gửi
- [ ] Đăng ký file thứ 11 → `400`; file > 50MB → `422`
- [ ] `total_points_awarded = 50` sau khi cả 2 sub-task `COMPLETED`
- [ ] Tạo task bỏ trống `company_id` (hoặc id không tồn tại) → vẫn `200`, resolve về company placeholder
- [ ] Xóa task có sub-task/submission mà không `force` → `400`; kèm `force=true` → `204` và cascade đúng
- [ ] Xóa task có evidence claim → luôn `400`, kể cả `force=true`
- [ ] `pytest app/tests/unit/test_task_service.py app/tests/unit/test_task_review.py app/tests/unit/test_task_submission_extras.py` pass

## 4. AI Task Builder

Phụ thuộc `task` (tạo `Task`/`Company` thật) và `chatbot` (gọi AI thật mỗi lượt — không tất định, có thể cần thêm 1-2 lượt tùy phản hồi model).

**Độ bền khi AI trả lời sai định dạng**: mỗi lượt gọi `chatbot.complete(..., json_mode=True)` — provider được yêu cầu ép JSON ở tầng API (`response_format`/`response_mime_type`), không chỉ dựa vào prompt. Nếu model vẫn trả prose/text (từng gây `400 "... was not valid JSON"` và làm hội thoại kẹt ở `COLLECTING` vĩnh viễn), service tự động retry 1 lần với message sửa lỗi; nếu retry vẫn thất bại, lượt đó trả `200` với 1 AI message xin lỗi/yêu cầu diễn đạt lại thay vì `400` — hội thoại không bao giờ bị kẹt chỉ vì 1 lượt AI trả sai định dạng. Xem `TaskBuilderService._complete_and_parse`.

**Giới hạn 3 câu hỏi làm rõ** (`MAX_CLARIFYING_QUESTIONS`): AI được yêu cầu (qua system prompt) hỏi tối đa 3 câu; sau vòng thứ 3, service tự chèn `QUESTION_LIMIT_INSTRUCTION` vào lượt gọi tiếp theo, buộc AI chốt `status: "ready"` ngay dù thông tin còn thiếu, thay vì hỏi vô hạn.

**`confirm: true` — chốt sớm theo yêu cầu enterprise** (`POST .../messages`): enterprise không cần đợi đủ 3 vòng hỏi hay cung cấp brief/document đầy đủ — gửi `confirm: true` ở bất kỳ lượt nào để buộc AI đề xuất task ngay (`USER_CONFIRMED_INSTRUCTION`), tự suy luận giá trị hợp lý cho phần còn thiếu.

```bash
curl -X POST http://127.0.0.1:8000/tasks/companies/ -d '{"name":"LexNova","slug":"lexnova"}'
curl -X POST http://127.0.0.1:8000/task-builder/conversations \
  -d '{"company_id": <id>, "created_by": "user_enterprise_01", "message": "Toi can dich 1 van ban phap ly dai 10 trang."}'
```
**Kỳ vọng**: `status: "COLLECTING"`, `open_questions` không rỗng. Trả lời tiếp qua `POST /task-builder/conversations/{id}/messages` cho tới khi `status: "READY"` và `proposed_versions` có `complexity_level` (T1/T2/T3 — **không còn** field `difficulty` cũ), `version_label` (vd. "L1"). Hoặc chốt ngay bằng `confirm`:
```bash
curl -X POST http://127.0.0.1:8000/task-builder/conversations/<id>/messages \
  -d '{"message": "Tao task luon di", "confirm": true}'
```
**Kỳ vọng**: `status: "READY"` ngay cả khi mới trả lời 1 câu — `proposed_versions` vẫn có đủ field, phần thiếu do AI tự suy luận.

```bash
curl -X POST http://127.0.0.1:8000/task-builder/conversations/<id>/generate-task -d '{"selected_version": "L1"}'
```
**Kỳ vọng**: `created_task` khớp phiên bản đã chọn; `review_status: PENDING_MENTOR_APPROVAL` (vẫn phải qua duyệt mentor bình thường, không bypass). Nếu phiên bản AI đề xuất còn thiếu `complexity_level`/giờ ước tính/điểm năng lực (thường gặp sau `confirm: true`), các field này tự điền mặc định (`T1`/1/4/10 — `VERSION_FIELD_DEFAULTS`) thay vì trả lỗi; chỉ `title`/`context` là bắt buộc thật sự, thiếu 1 trong 2 mới `400`.

**`sub_tasks` (kể từ khi bật AI planning cho generate_task)**: `generate_task` gọi `TaskService.create_task(..., skip_ai_planning=False)` — task tạo ra vẫn đi qua `_ai_plan_subtasks` như task tạo thủ công, nên `GET /tasks/{created_task.id}` có thể trả về `sub_tasks: []` (task đủ gọn) hoặc vài sub-task (nếu AI thấy phiên bản quá rộng cho 1 lần nộp) — không tất định, phụ thuộc model. `complexity_level` đã chọn qua hội thoại **không** bị AI ghi đè (`override_complexity=False` khi `complexity_level` đã có sẵn).

### Checklist
- [ ] `status` chuyển đúng `COLLECTING → READY → TASK_CREATED`
- [ ] `generate-task` khi chưa `READY` → `400`; `selected_version` không tồn tại → `400`
- [ ] Task tạo ra có `review_status: PENDING_MENTOR_APPROVAL`; `complexity_level` khớp đúng phiên bản đã chọn (không bị AI planning ghi đè)
- [ ] Gửi `confirm: true` ở lượt đầu tiên → `status: "READY"` ngay, không cần đủ 3 vòng hỏi
- [ ] `generate-task` với phiên bản thiếu `complexity_level`/giờ/điểm → vẫn `200`, tự điền mặc định; thiếu `title`/`context` → vẫn `400`
- [ ] `pytest app/tests/unit/test_task_builder_service.py` pass

## 5. Evidence (bằng chứng năng lực)

Độc lập về mặt code với `task`/`student`, nhưng dữ liệu tham chiếu `task_id`/`skill_id` phải tồn tại thật (FK).

```bash
curl -X POST http://127.0.0.1:8000/evidence/ \
  -H "Content-Type: application/json" \
  -d '{"student_id":1001,"skill_id":1,"task_id":1,"claim":"Sinh vien lam sach du lieu dung logic","task_complexity":"T1","risk_level":"R0","proposed_skill_level":"L1"}'
```
**Kỳ vọng**: `status: "AI_DRAFT"`.

```bash
CLAIM_ID=<id trả về>
curl -X POST http://127.0.0.1:8000/evidence/$CLAIM_ID/student-review     # -> STUDENT_REVIEWED
curl -X POST http://127.0.0.1:8000/evidence/$CLAIM_ID/submit-to-mentor  # -> PENDING_MENTOR
curl -X POST http://127.0.0.1:8000/evidence/$CLAIM_ID/mentor-decision \
  -d '{"mentor_id": 1, "decision": "VERIFIED", "comment": "Xac nhan"}'
```
**Kỳ vọng quan trọng**: chỉ `decision: "VERIFIED"` mới cập nhật `StudentSkillProfile` (qua `StudentProfileService.create_student_skill_event`). Kiểm tra:
```bash
curl http://127.0.0.1:8000/students/1001/skills
curl http://127.0.0.1:8000/students/1001/skill-events
```
**Kỳ vọng**: có 1 skill event mới với `source_service: "student_service"`, `source_ref: "evidence_claim:<CLAIM_ID>"`.

Test `REJECTED`/`NEED_MORE_EVIDENCE` (tạo claim khác, lặp lại tới `submit-to-mentor`, rồi `mentor-decision` với `decision: "REJECTED"`) → xác nhận **không** có skill event mới nào được tạo.

Gọi sai thứ tự (vd. `submit-to-mentor` khi còn `AI_DRAFT`) → `400` kèm lý do rõ ràng.

### Checklist
- [ ] State machine đúng thứ tự: `AI_DRAFT → STUDENT_REVIEWED → PENDING_MENTOR → VERIFIED`
- [ ] Chỉ `VERIFIED` mới tạo skill event mới; `REJECTED`/`NEED_MORE_EVIDENCE` không đụng skill profile
- [ ] Gọi sai thứ tự state machine → `400`
- [ ] `pytest app/tests/unit/test_evidence_service.py` pass

### 5.1 Evidence tự động khi hoàn thành task, và career recommendation (domain `student`)

Nếu task ở mục 3 có link `TaskSkill` (tự động lúc tạo, hoặc thủ công qua `PUT /tasks/{id}/skills`), bước `complete` (hoặc `mentor-review` approve, hoặc `auto-check` khi task không cần mentor) tự tạo sẵn 1 `EvidenceClaim` `AI_DRAFT` cho mỗi skill đó — không cần tự `POST /evidence/` nữa cho các skill đã khai báo trên task:
```bash
curl http://127.0.0.1:8000/evidence/students/$STUDENT   # đã thấy claim AI_DRAFT xuất hiện ngay sau /complete
```
Claim này vẫn phải tự đi `student-review` → `submit-to-mentor` → `mentor-decision` như bình thường — không có gì tự `VERIFIED`.

Mỗi lần 1 submission chuyển sang `COMPLETED` (bất kỳ trong 3 đường ở mục 3), server tự lên lịch (`BackgroundTasks`) chạy `refresh_career_recommendations` — gọi LLM xếp hạng lại nghề nghiệp phù hợp cho student đó, `persist=true`. Tín hiệu skill đưa vào prompt chỉ lấy từ `StudentSkillProfile` đã `VERIFIED` — task hoàn thành mà chưa evidence nào được mentor xác nhận thì recommendation sẽ từ chối tạo (`400`, tiếng Việt: "chưa có kỹ năng nào được xác thực"):
```bash
curl -X POST http://127.0.0.1:8000/students/$STUDENT/career-recommendations/generate -d '{"limit": 5, "persist": true}'
curl http://127.0.0.1:8000/students/$STUDENT/career-recommendations
```
**Kỳ vọng**: gọi `generate` trước khi có `StudentSkillProfile` nào (chỉ có task `COMPLETED`, chưa evidence `VERIFIED`) → `400`; sau khi ít nhất 1 evidence đã `VERIFIED` → `200`, mỗi recommendation có `rationale`/`strengths`/`gaps`/`next_steps`; gọi `generate` lần 2 cho cùng student/career → cập nhật row cũ (`score` mới) thay vì tạo thêm dòng trùng.

### Checklist (5.1)
- [ ] `/complete`, `/mentor-review` (approve), `/auto-check` (auto-complete) đều tự tạo `EvidenceClaim AI_DRAFT` cho skill đã link trên task
- [ ] `career-recommendations/generate` khi chưa có `StudentSkillProfile` nào → `400`
- [ ] Sau khi có ít nhất 1 skill `VERIFIED` → `generate` thành công, gọi lại không tạo trùng recommendation cho cùng 1 career
- [ ] `pytest app/tests/integration/test_task_skill_evidence.py app/tests/integration/test_student_career_recommendations.py` pass

## 6. ePortfolio

```bash
curl http://127.0.0.1:8000/eportfolio/students/1001
```
**Kỳ vọng**: `verified_skills`, `verified_evidence` (chỉ claim đã `VERIFIED`), `completed_tasks`, `career_suggestions`, `suggested_next_tasks`, `share_with_business: false` (mặc định).

Business view khi chưa consent:
```bash
curl http://127.0.0.1:8000/eportfolio/students/1001/business-view
# -> 403: chưa opt-in share_with_business
```

Bật consent rồi thử lại:
```bash
curl -X PUT http://127.0.0.1:8000/eportfolio/students/1001/share-settings -d '{"share_with_business": true}'
curl http://127.0.0.1:8000/eportfolio/students/1001/business-view
```
**Kỳ vọng**: `200`, response **không** chứa field nào ngoài `student_id/full_name/headline/verified_skills/selected_evidence/selected_tasks` (không lộ raw AI chat/private reflection — xem [requirements.md §21](requirements.md#21-eportfolio-requirements)).

### Checklist
- [ ] Business view `403` khi chưa consent, `200` sau khi bật `share_with_business`
- [ ] `verified_evidence`/`verified_skills` chỉ phản ánh evidence đã `VERIFIED`, không lộ `AI_DRAFT`/`PENDING_MENTOR`

## 7. Luồng tích hợp end-to-end (toàn bộ Core Product Flow)

Tái hiện đúng [requirements.md §3](requirements.md#3-core-product-flow) xuyên suốt 4 domain, xác nhận dữ liệu thực sự chảy qua toàn hệ thống chứ không phải các domain rời rạc:

1. `POST /tasks/companies/` — tạo company.
2. `POST /tasks/` với `skip_ai_planning: true` — tạo task, `review_status: PENDING_MENTOR_APPROVAL`.
3. `POST /tasks/{id}/review` với `decision: APPROVED` — mentor duyệt.
4. `POST /tasks/{id}/join` — student nhận task, `joined_at` được ghi (= `accepted_at` của MVP).
5. `POST /tasks/{id}/submit` kèm `student_reflection` — student nộp bài, `submitted_at`/`elapsed_seconds` được ghi.
6. `POST /tasks/submissions/{id}/mentor-review` — mentor duyệt submission + feedback.
7. `POST /evidence/` — tạo evidence claim (`AI_DRAFT`) tham chiếu đúng `task_id`/`skill_id` ở bước 2.
8. `POST /evidence/{id}/student-review` → `submit-to-mentor` → `mentor-decision` (`VERIFIED`) — mentor xác nhận bằng chứng, `StudentSkillProfile` được cập nhật.
9. `GET /eportfolio/students/{id}` — xác nhận evidence vừa verify xuất hiện trong `verified_evidence`, `completed_tasks` (sau khi `complete` submission ở bước 6), và skill level mới trong `verified_skills`.

Đây là bằng chứng cho nguyên tắc lõi ở [requirements.md §40](requirements.md#40-nguyên-tắc-chung-cho-3-team): `AI proposes → Human reviews → System records → Student owns evidence`.

## 8. Alembic — migration

Schema version hóa ở `app/alembic/`. Lệnh chạy từ `app/` (để `alembic.ini` resolve đúng):

```bash
cd app
alembic upgrade head              # áp dụng migration mới nhất — bắt buộc cho production/staging
alembic revision --autogenerate -m "mo ta thay doi"   # tạo migration mới sau khi sửa models.py
alembic downgrade -1              # rollback 1 bước
alembic current                    # xem revision hiện tại của DB đang trỏ tới
```

**DB đã có sẵn schema từ `create_all()` cũ** (chưa từng chạy alembic lần nào) — KHÔNG chạy `upgrade head` thẳng (sẽ lỗi "table already exists"). Thay vào đó, đánh dấu DB đã ở baseline mà không chạy lại migration:

```bash
alembic stamp head
```

Sau bước này, `alembic upgrade head` là cách duy nhất được phép đổi schema về sau.

**DB stamped ở revision không còn tồn tại trong lịch sử** (vd. sau khi squash nhiều migration cũ thành 1 baseline, `alembic_version` trên DB vẫn trỏ tới revision id cũ đã bị xóa) — `alembic upgrade head`/`alembic stamp <rev>` thường sẽ báo `Can't locate revision identified by '...'`. Dùng `--purge` để ghi đè thẳng, bỏ qua việc validate lịch sử cũ (chỉ an toàn khi đã tự xác nhận bằng tay — vd. so cột thật trên DB với `Base.metadata` — rằng schema thật sự khớp với revision sắp stamp vào, trừ đúng phần sẽ được migration tiếp theo xử lý):

```bash
alembic stamp --purge <revision_baseline_hợp_lệ>
alembic upgrade head
```

`AUTO_CREATE_SCHEMA=true` (mặc định trong `app/core/config.py`) là lớp tiện lợi dev/demo phía trên Alembic — `main.py` tự `Base.metadata.create_all()` lúc startup nếu bảng còn thiếu. Set `AUTO_CREATE_SCHEMA=false` ở môi trường chia sẻ/production để tránh 2 cơ chế đổi schema chồng nhau.

## 9. Docker / Deploy

```bash
docker build -t career-guidance .
docker run -p 8080:8080 -e DATABASE_URL="postgresql://..." career-guidance
```

Image build bằng `uv sync --frozen --no-dev`. `.env` không copy vào image — truyền secret qua `--set-secrets` (Cloud Run + Secret Manager). Container lắng nghe `$PORT` Cloud Run tiêm vào runtime.

```bash
gcloud run deploy career-guidance \
  --source . \
  --region asia-southeast1 \
  --set-secrets DATABASE_URL=career-guidance-db-url:latest \
  --allow-unauthenticated
```

Nhớ set `ENABLE_SEED_ENDPOINT=false` và `AUTO_CREATE_SCHEMA=false` trên production — 2 biến này chỉ nên `true` ở dev/demo.
