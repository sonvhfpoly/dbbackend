# Test Plan: Task Marketplace (`domains/task`)

Hướng dẫn test end-to-end domain `task` — nhiệm vụ thực hành do doanh nghiệp tài trợ, hỗ trợ sub-task, workflow nộp/duyệt/chấm điểm đầy đủ trạng thái. Xem thiết kế data model tại [TASK_DATA_MODEL.md](TASK_DATA_MODEL.md), hướng dẫn chạy server tại [README.md](README.md). Domain này **độc lập** với `market`/`guidance` — không cần seed domain nào khác trước.

## 0. Chuẩn bị

```bash
cd app
uv run --project .. uvicorn main:app --reload --port 8000
```

Mở Swagger UI: http://127.0.0.1:8000/docs, tag **Task Marketplace**. Mọi bước dưới đây làm được qua "Try it out" hoặc `curl` như liệt kê.

---

## 1. Seed dữ liệu mẫu

```bash
curl -X POST http://127.0.0.1:8000/tasks/seed-demo-data
```

**Kỳ vọng (lần đầu, DB trống)**: `{"company_id":1,"root_task_id":1,"root_task_created":true,"sub_tasks_created":2}`. Gọi lại lần 2 trở đi: `root_task_created`/`sub_tasks_created` sẽ là `false`/`0` (idempotent theo `slug` công ty và `title` task) — không phải lỗi.

Tạo ra: 1 `Company` ("Tiki Corporation"), 1 task gốc **không có điểm riêng** ("Phân tích Hành vi Giỏ hàng E-commerce"), và 2 sub-task:
- Sub-task 1 — "Làm sạch & khám phá dữ liệu" — **20 điểm**, chỉ cần `auto-check` (không cần mentor).
- Sub-task 2 — "Xác định Drop-off Point & Xây Dashboard" — **30 điểm**, cần `mentor-review`, có 2 tiêu chí đánh giá (60% + 40%).

Ghi lại `root_task_id`. Lấy id 2 sub-task qua:

```bash
curl http://127.0.0.1:8000/tasks/1 | python -m json.tool
```

Xem field `sub_tasks[].id` — gọi tắt là `SUB1_ID`/`SUB2_ID` trong các bước dưới.

### Checklist bước 1
- [ ] Task gốc trả về `competency_points: null` (vì có sub-task)
- [ ] `sub_tasks` có đúng 2 phần tử, `competency_points` là `20` và `30`
- [ ] Tổng `weight_percent` của `criteria` mỗi sub-task = 100

---

## 2. Validate khi tạo task

**Chặn lồng sub-task quá 2 cấp** — thử tạo task với `parent_task_id` trỏ vào một **sub-task** (không phải task gốc):

```bash
curl -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Invalid nested","difficulty":"EASY","company_id":1,"parent_task_id":<SUB1_ID>,"estimated_hours_min":1,"estimated_hours_max":1,"competency_points":5,"context":"test"}'
```

**Kỳ vọng**: `400` — `"Task <SUB1_ID> is already a sub-task; nesting is limited to 2 levels"`.

**Chặn tiêu chí đánh giá không tổng 100%**:

```bash
curl -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Bad weights","difficulty":"EASY","company_id":1,"estimated_hours_min":1,"estimated_hours_max":1,"competency_points":10,"context":"test","criteria":[{"criterion":"a","weight_percent":60},{"criterion":"b","weight_percent":30}]}'
```

**Kỳ vọng**: `400` — `"Evaluation criteria weights must sum to 100, got 90"`.

### Checklist bước 2
- [ ] Cả 2 request trên trả `400`, không phải `500`/crash
- [ ] Message lỗi nêu rõ nguyên nhân (không phải generic "Bad Request")

---

## 3. Luồng A — chỉ cần Auto-Check (sub-task 1, 20 điểm)

```bash
STUDENT=1001

# Tham gia
curl -X POST http://127.0.0.1:8000/tasks/<SUB1_ID>/join \
  -H "Content-Type: application/json" -d "{\"student_id\": $STUDENT}"
# -> lấy "id" trong response, gọi là SUB1_SUBMISSION_ID

# Nộp báo cáo — theo task_id + student_id, KHÔNG cần biết submission_id
curl -X POST http://127.0.0.1:8000/tasks/<SUB1_ID>/submit \
  -H "Content-Type: application/json" -d "{\"student_id\": $STUDENT, \"report_url\": \"https://example.com/report.csv\"}"

# Auto-check
curl -X POST http://127.0.0.1:8000/tasks/submissions/<SUB1_SUBMISSION_ID>/auto-check

# Hoàn thành (AI tự submit, vì requires_mentor_approval=false)
curl -X POST http://127.0.0.1:8000/tasks/submissions/<SUB1_SUBMISSION_ID>/complete \
  -H "Content-Type: application/json" -d '{"completed_by": "AI"}'
```

**Kỳ vọng**: mỗi bước trả về đúng `status` kế tiếp (`JOINED` → `SUBMITTED` → `AUTO_CHECK_PASSED` → `COMPLETED`), bước cuối có `points_awarded: 20`, `completed_by: "AI"`.

**Test idempotency của join** — gọi lại `POST .../join` với cùng `student_id`: phải trả về **cùng `id` submission** đã có (không tạo bản ghi mới), kể cả sau khi đã `COMPLETED`.

### Checklist bước 3
- [ ] `join` gọi 2 lần trả về cùng 1 submission `id`
- [ ] `complete` trả `points_awarded: 20`
- [ ] Gọi `submit` lại sau khi đã `COMPLETED` → `400` (không cho nộp lại task đã xong)

---

## 4. Luồng B — cần Mentor Review + chấm điểm theo tiêu chí (sub-task 2, 30 điểm)

```bash
# Tham gia + nộp
curl -X POST http://127.0.0.1:8000/tasks/<SUB2_ID>/join -H "Content-Type: application/json" -d "{\"student_id\": $STUDENT}"
curl -X POST http://127.0.0.1:8000/tasks/<SUB2_ID>/submit -H "Content-Type: application/json" -d "{\"student_id\": $STUDENT, \"report_url\": \"https://example.com/report2.pdf\"}"

# Thử complete SỚM (trước khi mentor duyệt) -> phải bị chặn
curl -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/tasks/submissions/<SUB2_SUBMISSION_ID>/complete -H "Content-Type: application/json" -d '{"completed_by": "MENTOR"}'

# Mentor duyệt
curl -X POST http://127.0.0.1:8000/tasks/submissions/<SUB2_SUBMISSION_ID>/mentor-review \
  -H "Content-Type: application/json" -d '{"approved": true, "feedback": "Phân tích drop-off tốt"}'

# Chấm điểm từng tiêu chí (lấy criterion_id đúng từ GET /tasks/<SUB2_ID>, KHÔNG lấy nhầm criterion của sub-task khác)
curl -X POST http://127.0.0.1:8000/tasks/submissions/<SUB2_SUBMISSION_ID>/scores \
  -H "Content-Type: application/json" -d '{"criterion_id": <CRIT_60>, "score_percent": 90, "feedback": "Xác định đúng", "scored_by": "MENTOR"}'
curl -X POST http://127.0.0.1:8000/tasks/submissions/<SUB2_SUBMISSION_ID>/scores \
  -H "Content-Type: application/json" -d '{"criterion_id": <CRIT_40>, "score_percent": 85, "feedback": "Trình bày rõ", "scored_by": "MENTOR"}'

curl http://127.0.0.1:8000/tasks/submissions/<SUB2_SUBMISSION_ID>/scores

# Hoàn thành
curl -X POST http://127.0.0.1:8000/tasks/submissions/<SUB2_SUBMISSION_ID>/complete -H "Content-Type: application/json" -d '{"completed_by": "MENTOR"}'
```

**Kỳ vọng**:
- Complete sớm → `400` — `"Submission ... is 'SUBMITTED', expected one of: MENTOR_APPROVED"`.
- Chấm điểm với `criterion_id` thuộc task khác → `400` — `"Criterion ... does not belong to task ..."`.
- Chấm lại cùng `criterion_id` lần 2 → **update** score cũ (upsert), `GET .../scores` không có bản ghi trùng.
- Complete cuối cùng trả `points_awarded: 30`, `completed_by: "MENTOR"`.

### Checklist bước 4
- [ ] Complete trước khi mentor duyệt bị chặn đúng `400`
- [ ] Chấm điểm sai `criterion_id` (không thuộc task) bị chặn `400`
- [ ] Chấm lại cùng tiêu chí → không tạo row mới (kiểm tra `GET .../scores` chỉ có 1 record/tiêu chí)

---

## 5. Cộng dồn điểm ở task cha

```bash
curl "http://127.0.0.1:8000/tasks/<root_task_id>/progress?student_id=$STUDENT"
```

**Kỳ vọng** (sau khi hoàn thành cả 2 sub-task ở mục 3 và 4):

```json
{
  "task_id": <root_task_id>,
  "student_id": 1001,
  "is_fully_completed": true,
  "total_points_awarded": 50,
  "sub_tasks": [
    {"task_id": <SUB1_ID>, "status": "COMPLETED", "points_awarded": 20},
    {"task_id": <SUB2_ID>, "status": "COMPLETED", "points_awarded": 30}
  ],
  "submission": null
}
```

Thử với 1 `student_id` khác **chưa tham gia gì** (vd. `9999`): `is_fully_completed: false`, `total_points_awarded: 0`, mỗi sub-task có `status: null`.

### Checklist bước 5
- [ ] `total_points_awarded = 50` khi cả 2 sub-task đã `COMPLETED`
- [ ] `is_fully_completed = false` nếu chỉ 1 trong 2 sub-task hoàn thành
- [ ] Student chưa tham gia → không lỗi, trả về trạng thái rỗng hợp lệ (không phải `404`)

---

## 6. Lấy danh sách submissions

```bash
# Toàn bộ submission trên hệ thống — bỏ trống mọi filter
curl "http://127.0.0.1:8000/tasks/submissions"

# Lọc theo student, theo task, hoặc cả hai
curl "http://127.0.0.1:8000/tasks/submissions?student_id=$STUDENT"
curl "http://127.0.0.1:8000/tasks/submissions?task_id=<SUB1_ID>"
curl "http://127.0.0.1:8000/tasks/submissions?student_id=$STUDENT&task_id=<SUB1_ID>"
```

### Checklist bước 6
- [ ] Không truyền filter nào → trả về tất cả submission đã tạo trong các bước trước
- [ ] Lọc theo `student_id` hoặc `task_id` (hoặc cả hai) thu hẹp đúng kết quả

---

## 7. Chatbot tự đánh giá độ khó & tách sub-task khi tạo task gốc

Khi tạo một task **không có `parent_task_id`** (task gốc), service gọi chatbot để đánh giá lại `difficulty` và quyết định có nên tách thành sub-task hay không. Đây là best-effort: nếu chatbot lỗi/trả sai định dạng, task vẫn được tạo bình thường (không có sub-task tự động) — không có gì để "fail" ở bước này từ góc nhìn HTTP.

```bash
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Xay dung he thong phan tich hanh vi nguoi dung toan dien","difficulty":"MEDIUM","company_id":1,"estimated_hours_min":20,"estimated_hours_max":40,"context":"Can thu thap, lam sach, phan tich va truc quan hoa hanh vi nguoi dung tren nhieu kenh"}'
```

**Kỳ vọng**: response trả về ngay (không bị chặn dù chatbot chậm/lỗi). Gọi lại `GET /tasks/{id đã tạo}`:
- Nếu chatbot khả dụng và đánh giá task này đủ rộng để tách: `sub_tasks` có thêm các phần tử mới (`parent_task_id` = id task vừa tạo), và `competency_points` của task gốc là `null`.
- Nếu chatbot không khả dụng hoặc đánh giá không cần tách: task vẫn được tạo với đúng dữ liệu đã gửi, `sub_tasks` rỗng.

Tạo **sub-task thủ công** (truyền sẵn `parent_task_id`) thì KHÔNG kích hoạt lại bước gọi AI phân tách này (tránh đệ quy, và nesting vốn đã giới hạn 2 cấp).

**`difficulty` giờ là tùy chọn** (cả task gốc lẫn sub-task) — bỏ trống thì AI tự phân loại:

```bash
# Task gốc KHÔNG truyền difficulty
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Task khong co difficulty","company_id":1,"estimated_hours_min":2,"estimated_hours_max":4,"competency_points":10,"context":"Test AI tu dien difficulty"}'
# -> GET lai task vua tao: field "difficulty" phai co gia tri hop le (EASY/MEDIUM/HARD), khong phai null

# Task gốc CÓ truyền difficulty rõ ràng -> AI không được ghi đè
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Task co difficulty ro rang","difficulty":"HARD","company_id":1,"estimated_hours_min":2,"estimated_hours_max":4,"competency_points":10,"context":"Test AI khong duoc ghi de"}'
# -> GET lai: "difficulty" phai dung bang "HARD" nhu da truyen, du AI co the co y kien khac
```

### Checklist bước 7
- [ ] Tạo task gốc luôn thành công (201/200) bất kể chatbot có phản hồi hay không
- [ ] Nếu AI quyết định tách: sub-task được lưu đúng `parent_task_id`, task cha có `competency_points: null`
- [ ] Tạo sub-task thủ công (có `parent_task_id`) không gọi AI lại để tách sub-task
- [ ] Bỏ trống `difficulty` (task gốc hoặc sub-task) → AI tự điền, response không bao giờ có `difficulty: null`
- [ ] Truyền sẵn `difficulty` → giữ nguyên giá trị đã truyền, AI không ghi đè

---

## 8. Chạy test tự động (không cần DB)

```bash
uv run --project .. pytest app/tests/unit/test_task_service.py -v
```

**Kỳ vọng**: 19 test pass — bao gồm validate lồng sub-task > 2 cấp, validate tổng trọng số tiêu chí, 2 test cộng dồn điểm (`total_points_awarded` chỉ tính sub-task `COMPLETED`, `is_fully_completed` đúng khi đủ/thiếu), 1 test `submit_report` báo lỗi khi student chưa từng join, 5 test cho AI sub-task planning (tách khi `should_split=true`, no-op khi `false`, nuốt lỗi khi chatbot crash/trả JSON không hợp lệ, và không ghi đè difficulty khi `override_difficulty=False`), và 5 test cho việc tự động điền `difficulty` khi bỏ trống (`_ai_assess_difficulty` thành công/thất bại, và toàn bộ `create_task` cho cả sub-task lẫn task gốc).

---

## Checklist tổng hợp

- [ ] Seed idempotent (gọi 2 lần không lỗi, không tạo trùng company/task)
- [ ] Cả 2 luồng workflow (auto-check-only và mentor-review+scoring) chạy đúng state machine, không nhảy cóc được bước
- [ ] `join` idempotent — không tạo submission trùng cho cùng (task, student)
- [ ] `submit` theo (task_id, student_id) — không cần biết submission_id
- [ ] Chặn lồng sub-task > 2 cấp, chặn tổng trọng số tiêu chí ≠ 100%, chặn chấm điểm sai task
- [ ] Cộng dồn điểm task cha đúng và chỉ tính submission `COMPLETED`
- [ ] `GET /tasks/submissions` trả đúng khi lọc theo `student_id`/`task_id`/không lọc gì
- [ ] Tạo task gốc kích hoạt AI đánh giá độ khó + tách sub-task (best-effort, không chặn việc tạo task)
- [ ] `pytest app/tests/unit/test_task_service.py` pass toàn bộ (13 test)
