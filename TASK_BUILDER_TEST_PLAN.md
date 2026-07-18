# Test Plan: AI Task Builder (`domains/task_builder`)

Hướng dẫn test end-to-end tính năng "tạo task bằng AI chat" (ENT-01) — doanh nghiệp chat nhiều lượt với AI, đính kèm tài liệu tham khảo, AI đề xuất 1+ phiên bản task, doanh nghiệp chọn 1 phiên bản để tạo `Task` thật. Xem thiết kế tại phần trao đổi trong session implement (không có file design riêng), hướng dẫn chạy server tại [README.md](README.md). Domain này **phụ thuộc** `domains/task` (tạo `Task`/`Company` thật qua `TaskRepository`) và `domains/chatbot` (gọi AI thật — Vertex AI hoặc FPT Cloud, xem [README.md](README.md) phần cấu hình provider).

## 0. Chuẩn bị

```bash
cd app
uv run --project .. uvicorn main:app --reload --port 8000
```

Mở Swagger UI: http://127.0.0.1:8000/docs, tag **AI Task Builder**.

Đảm bảo `app/.env` có:
- `DATABASE_URL` (bắt buộc).
- Ít nhất 1 AI provider khả dụng: `FPT_CLOUD_API_KEY`, **hoặc** ADC Vertex AI (`gcloud auth application-default login` + `VERTEX_PROJECT_ID`) — xem README. Không có provider nào → mọi bước gọi AI trả `503`.
- `TASK_BUILDER_GCS_BUCKET` — chỉ cần cho bước 4 (upload tài liệu). Bỏ qua bước đó nếu chưa có bucket.

⚠️ **Khác với `TASK_TEST_PLAN.md`**: domain này gọi AI thật ở mỗi lượt chat — nội dung `reply`/số lượt cần thiết để AI chuyển sang `READY` **không tất định** (tùy model). Các bước dưới đưa ra câu trả lời đủ rõ ràng để nudge AI chuyển trạng thái nhanh, nhưng có thể cần thêm 1-2 lượt tùy phản hồi thực tế của model.

---

## 1. Tạo company

Tái sử dụng endpoint có sẵn của domain `task`:

```bash
curl -X POST http://127.0.0.1:8000/tasks/companies/ \
  -H "Content-Type: application/json" \
  -d '{"name":"LexNova","slug":"lexnova"}'
```

Ghi lại `id` trong response, gọi tắt là `COMPANY_ID`.

---

## 2. Bắt đầu hội thoại

```bash
curl -X POST http://127.0.0.1:8000/task-builder/conversations \
  -H "Content-Type: application/json" \
  -d '{"company_id": <COMPANY_ID>, "created_by": "user_enterprise_01", "message": "Tôi cần dịch một văn bản pháp lý dài 10 trang từ tiếng Anh sang tiếng Việt."}'
```

**Kỳ vọng**: `200`, response có `conversation_id`, `status: "COLLECTING"`, `reply` là câu hỏi làm rõ của AI (ví dụ hỏi mục đích sử dụng/dữ liệu thật hay giả lập), `open_questions` không rỗng, `proposed_versions: []`.

Ghi lại `conversation_id`.

### Checklist bước 2
- [ ] `status` là `COLLECTING` (chưa đủ thông tin để AI đề xuất ngay)
- [ ] `open_questions` không rỗng khi `status=COLLECTING`

---

## 3. Trả lời để AI đủ thông tin đề xuất

```bash
curl -X POST http://127.0.0.1:8000/task-builder/conversations/<conversation_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Đây là tài liệu mô phỏng dùng để đánh giá sinh viên, không phải mục đích pháp lý chính thức, toàn bộ dữ liệu (tên người, công ty) là giả lập."}'
```

Nếu AI vẫn hỏi thêm (`status` vẫn `COLLECTING`), tiếp tục trả lời (ví dụ: "Sản phẩm đầu ra là bản dịch tiếng Việt kèm chú thích thuật ngữ") cho tới khi `status` chuyển `"READY"`.

**Kỳ vọng khi `status="READY"`**: `proposed_versions` có ít nhất 1 phần tử, mỗi phần tử có đủ `version_label`, `title`, `context`, `difficulty`, `estimated_hours_min/max`, `competency_points`. `open_questions` rỗng.

### Checklist bước 3
- [ ] `status` chuyển từ `COLLECTING` → `READY` sau khi cung cấp đủ thông tin
- [ ] Mỗi phần tử `proposed_versions` có `version_label` duy nhất (vd. `L1`, `L2`) để dùng ở bước 6

---

## 4. (Tuỳ chọn) Upload tài liệu tham khảo

Chỉ chạy nếu đã cấu hình `TASK_BUILDER_GCS_BUCKET`:

```bash
curl -X POST http://127.0.0.1:8000/task-builder/conversations/<conversation_id>/documents \
  -F "file=@/duong/dan/toi/vanban.pdf;type=application/pdf"
```

**Kỳ vọng**: `200`, response có `id`, `storage_url` dạng `gs://<bucket>/task-builder/<conversation_id>/...`, `extracted_text_length > 0` (nếu file có text trích xuất được).

Gửi thêm 1 message bất kỳ sau đó (bước 3) để xác nhận AI có tham chiếu nội dung tài liệu trong `reply`.

**Chưa cấu hình bucket** → kỳ vọng `503` với `detail` nhắc `TASK_BUILDER_GCS_BUCKET` chưa được set.

### Checklist bước 4
- [ ] Upload thành công trả về `storage_url` hợp lệ, `extracted_text_length > 0` với file PDF/DOCX có chữ
- [ ] Chưa cấu hình bucket → `503`, không phải `500`/crash

---

## 5. Xem danh sách câu hỏi cần confirm (read-only, không gọi AI)

```bash
curl http://127.0.0.1:8000/task-builder/conversations/<conversation_id>/open-questions
```

**Kỳ vọng**: phản ánh đúng trạng thái của lượt AI **gần nhất** đã lưu trong DB (không tạo thêm lượt gọi AI mới — gọi lại nhiều lần liên tiếp phải trả kết quả giống hệt nhau, khác với bước 2/3).

### Checklist bước 5
- [ ] Gọi lại 2-3 lần liên tiếp → response giống hệt nhau (xác nhận không gọi AI ngầm)
- [ ] Sau bước 3 (status=READY), endpoint này trả đúng `proposed_versions` đã đề xuất

---

## 6. Tạo Task thật từ phiên bản đã chọn

```bash
curl -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/task-builder/conversations/<conversation_id>/generate-task \
  -H "Content-Type: application/json" \
  -d '{"selected_version": "L1"}'
```

**Kỳ vọng**: `200`, response có `status: "TASK_CREATED"`, `created_task` là 1 `Task` đầy đủ field (khớp `title`/`context`/`difficulty`/hours/points với `proposed_versions[0]` ở bước 3), `ai_message` là câu xác nhận (không phải lỗi/rỗng).

Xác nhận qua domain `task` có sẵn:

```bash
curl http://127.0.0.1:8000/tasks/<created_task.id>
```

**Kỳ vọng quan trọng**: `sub_tasks: []` — task được tạo **không** bị AI tự động tách thêm sub-task (vì `generate-task` cố tình bỏ qua bước AI re-planning của `TaskService.create_task`, xem comment trong `service.py`). `requires_mentor_approval: true` (giá trị mặc định).

### Checklist bước 6
- [ ] `created_task` khớp đúng nội dung phiên bản đã chọn ở bước 3
- [ ] `GET /tasks/{id}` cho thấy `sub_tasks` rỗng — **không** có sub-task nào bị tự động sinh thêm
- [ ] `requires_mentor_approval: true` — task đi qua luồng duyệt mentor sẵn có, không bypass

---

## 7. Xem lại toàn bộ lịch sử hội thoại

```bash
curl http://127.0.0.1:8000/task-builder/conversations/<conversation_id> | python -m json.tool
```

**Kỳ vọng**: `messages` liệt kê đủ theo thứ tự thời gian (enterprise/ai xen kẽ), lượt `ai` cuối cùng là message xác nhận tạo task từ bước 6. `documents` (nếu có upload ở bước 4) liệt kê đủ, không lộ toàn bộ `extracted_text` (chỉ có `extracted_text_length`).

### Checklist bước 7
- [ ] Thứ tự message đúng theo thời gian, không thiếu lượt nào
- [ ] Message xác nhận tạo task (bước 6) xuất hiện ở cuối, `role: "ai"`

---

## 8. Edge case — validate lỗi

**Tạo task khi hội thoại chưa `READY`** (dùng 1 conversation mới, chỉ gửi 1 message rồi gọi ngay `generate-task`):

```bash
curl -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/task-builder/conversations/<new_conversation_id>/generate-task \
  -H "Content-Type: application/json" -d '{"selected_version": "L1"}'
```

**Kỳ vọng**: `400` — `"Conversation ... is 'COLLECTING', expected 'READY' before generating a task"`.

**Chọn `version_label` không tồn tại** (dùng conversation đã `READY` ở bước 3, chọn version không có trong `proposed_versions`):

```bash
curl -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/task-builder/conversations/<conversation_id>/generate-task \
  -H "Content-Type: application/json" -d '{"selected_version": "L9"}'
```

**Kỳ vọng**: `400` — `"Version 'L9' not found in the latest proposal (available: ...)"`.

**Conversation không tồn tại**:

```bash
curl -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/task-builder/conversations/999999
```

**Kỳ vọng**: `404`.

### Checklist bước 8
- [ ] `generate-task` khi chưa `READY` → `400`, không tạo task
- [ ] `selected_version` không khớp → `400`, liệt kê rõ các version khả dụng
- [ ] `conversation_id` không tồn tại → `404` (áp dụng cho mọi endpoint theo `conversation_id`)

---

## 9. Chạy test tự động (không cần DB, không gọi AI thật)

```bash
uv run --project .. pytest app/tests/unit/test_task_builder_service.py -v
```

**Kỳ vọng**: 8 test pass — parse JSON hợp lệ/kèm markdown fence/JSON lỗi, đọc `open-questions` không gọi AI, và 4 test cho `generate_task` (chặn khi chưa `READY`, chặn version không tồn tại, chặn thiếu field bắt buộc, tạo đúng 1 task).

Chạy toàn bộ test suite (kèm các domain khác) để đảm bảo không có regression:

```bash
uv run --project .. pytest -q
```

**Kỳ vọng**: 60 test pass.

---

## Checklist tổng hợp

- [ ] Hội thoại chuyển đúng trạng thái `COLLECTING` → `READY` → `TASK_CREATED`
- [ ] `open-questions` là read-only, không gọi AI, phản ánh đúng lượt gần nhất trong DB
- [ ] Upload tài liệu (nếu có bucket) lưu đúng GCS + trích xuất text, AI tham chiếu được nội dung ở lượt sau
- [ ] `generate-task` tạo **đúng 1** task khớp phiên bản đã chọn, **không** tự động sinh thêm sub-task
- [ ] Task tạo ra vẫn đi qua luồng `requires_mentor_approval` sẵn có của domain `task`
- [ ] Toàn bộ edge case (chưa `READY`, version sai, conversation không tồn tại) trả đúng mã lỗi, có message rõ ràng
- [ ] `pytest app/tests/unit/test_task_builder_service.py` pass toàn bộ (8 test)
- [ ] `pytest -q` (toàn repo) pass toàn bộ (60 test), không có regression ở domain khác
