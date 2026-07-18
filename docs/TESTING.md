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

83 test hiện có, chia theo file:

| File | Domain | Nội dung |
|---|---|---|
| `test_market_service.py` | market | Ingestion, trend calculation, skill/job resolution |
| `test_anti_bias.py` | guidance | `DiversityValidator`/`RegionExpansionValidator` |
| `test_task_service.py` | task | AI complexity/sub-task planning, nesting depth, progress rollup, `skip_ai_planning` |
| `test_task_review.py` | task | Risk-level gate (R2/R3 chặn APPROVED), `join_task` yêu cầu `APPROVED` |
| `test_task_submission_extras.py` | task | `elapsed_seconds`, `student_reflection`, giới hạn file upload |
| `test_task_builder_service.py` | task_builder | AI turn parsing, `generate_task` (qua `TaskService.create_task(skip_ai_planning=True)`) |
| `test_evidence_service.py` | evidence | State machine `AI_DRAFT→...→VERIFIED`, cập nhật skill profile chỉ khi `VERIFIED` |

Toàn bộ dùng pattern bypass DB session: `object.__new__(Service)` rồi gán `.repo`/`.chatbot` là fake object — test logic thuần, không cần DB/LLM thật. Xem code các file trên để viết test tương tự cho domain mới.

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

Sinh đề xuất (ghi lại `demo_student_id` từ response seed guidance):
```bash
curl -X POST "http://127.0.0.1:8000/guidance/students/<demo_student_id>/recommendations?count=3"
```

**Kỳ vọng**: mỗi recommendation có `reasoning_explanation` không rỗng, `path_id` nằm trong catalog đã seed, không đọc như một chỉ định bắt buộc. Đối chiếu nội dung giải thích với `market_trend` thật ở bước trên — đây là bằng chứng dữ liệu market thực sự chảy vào quyết định tư vấn.

### Checklist
- [ ] `market_trend` của ít nhất 1 career/job khác `STABLE`
- [ ] `skill-trend` có ít nhất 1 skill với `growth_rate` khác `null`
- [ ] Mỗi recommendation có `reasoning_explanation`, không có recommendation nào toàn cùng 1 `PathType` (anti-bias hoạt động)
- [ ] `pytest app/tests/unit/test_anti_bias.py app/tests/unit/test_market_service.py` pass

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

Đăng ký file đã upload (metadata only — binary tự lo ở pipeline upload riêng, xem [requirements.md §14](requirements.md#14-file-upload-requirements)):
```bash
SUB1_SUBMISSION_ID=<id trả về ở bước join>
curl -X POST http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID/files \
  -H "Content-Type: application/json" \
  -d '{"file_name":"report.csv","mime_type":"text/csv","size_bytes":204800,"file_url":"https://storage.example.com/report.csv"}'
curl http://127.0.0.1:8000/tasks/submissions/$SUB1_SUBMISSION_ID/files
```
**Kỳ vọng**: đăng ký file thứ 11 cho cùng submission → `400` ("already has the maximum of 10 files"); `size_bytes` > 50MB → `422`.

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

### Checklist
- [ ] Task mới tạo (không seed) có `review_status: PENDING_MENTOR_APPROVAL`, `join` bị chặn cho tới khi `review` với `decision: APPROVED`
- [ ] `approved_risk: R2`/`R3` luôn bị chặn khi `decision: APPROVED`, dù risk gốc của task là gì
- [ ] `submit` trả `elapsed_seconds` hợp lệ và đúng `student_reflection` đã gửi
- [ ] Đăng ký file thứ 11 → `400`; file > 50MB → `422`
- [ ] `total_points_awarded = 50` sau khi cả 2 sub-task `COMPLETED`
- [ ] `pytest app/tests/unit/test_task_service.py app/tests/unit/test_task_review.py app/tests/unit/test_task_submission_extras.py` pass

## 4. AI Task Builder

Phụ thuộc `task` (tạo `Task`/`Company` thật) và `chatbot` (gọi AI thật mỗi lượt — không tất định, có thể cần thêm 1-2 lượt tùy phản hồi model).

**Độ bền khi AI trả lời sai định dạng**: mỗi lượt gọi `chatbot.complete(..., json_mode=True)` — provider được yêu cầu ép JSON ở tầng API (`response_format`/`response_mime_type`), không chỉ dựa vào prompt. Nếu model vẫn trả prose/text (từng gây `400 "... was not valid JSON"` và làm hội thoại kẹt ở `COLLECTING` vĩnh viễn), service tự động retry 1 lần với message sửa lỗi; nếu retry vẫn thất bại, lượt đó trả `200` với 1 AI message xin lỗi/yêu cầu diễn đạt lại thay vì `400` — hội thoại không bao giờ bị kẹt chỉ vì 1 lượt AI trả sai định dạng. Xem `TaskBuilderService._complete_and_parse`.

```bash
curl -X POST http://127.0.0.1:8000/tasks/companies/ -d '{"name":"LexNova","slug":"lexnova"}'
curl -X POST http://127.0.0.1:8000/task-builder/conversations \
  -d '{"company_id": <id>, "created_by": "user_enterprise_01", "message": "Toi can dich 1 van ban phap ly dai 10 trang."}'
```
**Kỳ vọng**: `status: "COLLECTING"`, `open_questions` không rỗng. Trả lời tiếp qua `POST /task-builder/conversations/{id}/messages` cho tới khi `status: "READY"` và `proposed_versions` có `complexity_level` (T1/T2/T3 — **không còn** field `difficulty` cũ), `version_label` (vd. "L1").

```bash
curl -X POST http://127.0.0.1:8000/task-builder/conversations/<id>/generate-task -d '{"selected_version": "L1"}'
```
**Kỳ vọng**: `created_task` khớp phiên bản đã chọn; `GET /tasks/{created_task.id}` cho thấy `sub_tasks: []` (không tự tách thêm — `generate_task` gọi `TaskService.create_task(..., skip_ai_planning=True)`) và `review_status: PENDING_MENTOR_APPROVAL` (vẫn phải qua duyệt mentor bình thường, không bypass).

### Checklist
- [ ] `status` chuyển đúng `COLLECTING → READY → TASK_CREATED`
- [ ] `generate-task` khi chưa `READY` → `400`; `selected_version` không tồn tại → `400`
- [ ] Task tạo ra có `sub_tasks: []` và `review_status: PENDING_MENTOR_APPROVAL`
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
