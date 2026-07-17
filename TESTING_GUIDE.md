# Hướng dẫn test luồng Dev 1 (Market Data) & Dev 3 (Guidance)

Tài liệu này hướng dẫn test end-to-end 2 domain đã hoàn thiện API: `market` (Dev 1) và `guidance` (Dev 3). Xem kiến trúc/thiết kế chi tiết tại [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), hướng dẫn cài đặt/chạy server tại [README.md](README.md).

**Thứ tự bắt buộc**: seed Dev 1 trước Dev 3 — `guidance` đọc `Career.market_trend` do `market` tính ra để đưa vào prompt AI, seed sai thứ tự vẫn chạy được nhưng phần "xu hướng thị trường" trong giải thích AI sẽ không có dữ liệu thật.

## 0. Chuẩn bị

```bash
cd app
uv run --project .. uvicorn main:app --reload --port 8000
```

Mở Swagger UI: http://127.0.0.1:8000/docs. Mọi bước dưới đây có thể làm qua "Try it out" trên Swagger, hoặc qua `curl` như liệt kê.

Đảm bảo `app/.env` có `DATABASE_URL` (bắt buộc) và `FPT_CLOUD_API_KEY` (bắt buộc riêng cho phần Dev 3, vì bước sinh recommendation gọi LLM thật).

---

## Phần 1 — Dev 1: Market Data

### 1.1. Seed dữ liệu mẫu

```bash
curl -X POST http://127.0.0.1:8000/market/seed-demo-data
```

**Kỳ vọng**: `{"skills_seeded":10,"careers_seeded":5,"job_postings_inserted":35}`.

Tạo sẵn 10 skill, 5 career (Backend/Frontend/Data Scientist/DevOps/Business Analyst), 35 job posting trải trên 4 thành phố (Hồ Chí Minh, Hà Nội, Đà Nẵng, Cần Thơ) với `posted_at` rải trong 60 ngày gần đây, và tự trigger tính `market_trend` ngay lập tức.

### 1.2. Kiểm tra career đang tăng/giảm trưởng

```bash
curl http://127.0.0.1:8000/market/careers/
```

**Kỳ vọng**: 5 career, `market_trend` là một trong `RISING`/`STABLE`/`DECLINING` (không phải toàn bộ `STABLE` mặc định — nếu thấy vậy nghĩa là bước tính trend chưa chạy, thử gọi lại `/market/jobs/bulk` bất kỳ để trigger background task, hoặc đợi vài giây rồi gọi lại vì trend được tính ở `BackgroundTasks` sau khi response trả về).

Lọc theo trend cụ thể:

```bash
curl "http://127.0.0.1:8000/market/careers/?trend=RISING"
```

### 1.3. Kiểm tra tín hiệu theo vùng miền + thời gian

```bash
curl "http://127.0.0.1:8000/market/analytics/skill-demand?location=Ho%20Chi%20Minh%20City"
curl "http://127.0.0.1:8000/market/analytics/skill-demand?location=Da%20Nang"
curl "http://127.0.0.1:8000/market/analytics/skill-trend?location=Ho%20Chi%20Minh%20City&window_days=30"
```

**Kỳ vọng**:
- Hồ Chí Minh có đủ 10 skill với demand > 0.
- Đà Nẵng gần như chỉ có `React` — đây là tín hiệu "thiếu hụt kỹ năng tại địa phương" theo yêu cầu đề bài (dữ liệu seed cố tình lệch vùng để minh hoạ).
- `skill-trend` trả về mảng `{skill, demand_recent, demand_previous, growth_rate}` — `growth_rate` là `null` khi `demand_previous = 0` (không chia cho 0, không bịa số).

### 1.4. (Tuỳ chọn) Test luồng thủ công thay vì seed

Nếu muốn tự tạo dữ liệu để hiểu rõ pipeline thay vì dùng seed có sẵn:

1. `POST /market/skills/` — tạo skill (`name`, `category`).
2. `POST /market/careers/` — tạo career, truyền `skill_ids` vừa tạo (đây là bước nối career với tín hiệu thị trường — thiếu bước này thì `market_trend` sẽ không bao giờ được tính vì không có skill nào để tính growth).
3. `POST /market/jobs/bulk` — nạp job posting, mỗi job cần `skill_ids` khớp với career muốn test; có thể truyền `posted_at` để giả lập dữ liệu quá khứ (kiểm tra "thay đổi theo thời gian").
4. Lặp lại bước 2 endpoint ở 1.2/1.3 để xem kết quả.

### Checklist Dev 1

- [ ] `market_trend` của ít nhất 1 career khác `STABLE`
- [ ] `skill-demand` khác nhau rõ rệt giữa 2 vùng (chứng minh phân tích theo khu vực)
- [ ] `skill-trend` có ít nhất 1 skill với `growth_rate` khác `null`

---

## Phần 2 — Dev 3: Guidance & Recommendation

### 2.1. Seed dữ liệu mẫu

```bash
curl -X POST http://127.0.0.1:8000/guidance/seed-demo-data
```

**Kỳ vọng (lần đầu, DB trống)**: `{"education_paths_created":6,"demo_student_id":<id>,"demo_student_created":true}`. Nếu DB đã được seed từ trước (gọi lại lần 2 trở đi), `education_paths_created` sẽ là `0` và `demo_student_created` là `false` — đây là hành vi đúng (idempotent theo tên/email), không phải lỗi; `demo_student_id` vẫn trả về id thật để dùng cho các bước sau. Ghi lại `demo_student_id`.

Tạo 6 `EducationPath` (đủ 3 loại `UNIVERSITY`/`VOCATIONAL`/`SHORT_COURSE`, một số gắn `location` cụ thể, một số `location: null` = học từ xa/toàn quốc) và 1 demo student ở **Cần Thơ** (cố tình chọn tỉnh không phải HCM/Hà Nội để có thể kiểm tra `RegionExpansionValidator`).

Kiểm tra catalog:

```bash
curl http://127.0.0.1:8000/guidance/education-paths/
```

### 2.2. Sinh đề xuất cho student

```bash
curl -X POST "http://127.0.0.1:8000/guidance/students/<demo_student_id>/recommendations?count=3"
```

**Kỳ vọng**: mảng `Recommendation`, mỗi phần tử có `path_id` (khớp 1 trong 6 path đã seed) và `reasoning_explanation` bằng tiếng Việt, nối được hồ sơ học sinh với xu hướng thị trường (ví dụ nhắc tới "Backend Developer đang tăng trưởng"). Nếu `count` ngoài khoảng 1–10, API trả `422`.

Lỗi thường gặp:
- `404` — `student_id` sai, không tồn tại.
- `400` "No education paths are configured yet" — chưa chạy bước 2.1.
- `503` — `FPT_CLOUD_API_KEY` chưa cấu hình trong `app/.env`.
- `502` — lỗi gọi FPT Cloud (xem `detail` để biết lý do thật: sai key, model không có quyền, hoặc bị chặn mạng — xem phần Troubleshooting của README nếu deploy trên Cloud Run).

### 2.3. Kiểm tra ràng buộc đạo đức (anti-bias) hoạt động thật

AI có thể tự trả về danh sách đã đa dạng sẵn (không có gì để `AntiBiasEngine` phải sửa) — đây **không phải lỗi**, engine chỉ can thiệp khi cần. Có 2 cách xác nhận validator hoạt động đúng:

**Cách 1 — quan sát trực tiếp (không đảm bảo lần nào cũng trigger vì AI không tất định):**
Gọi lại 2.2 vài lần với `count=2`, xem `path_id` trả về — nếu cùng `PathType` hoặc cùng `location` với `current_location` của student ("Can Tho"), so với lần gọi mà `AntiBiasEngine` đã can thiệp thì reasoning của path bị thay sẽ có nội dung dạng "Được bổ sung để...".

**Cách 2 — chạy unit test (đáng tin cậy, không phụ thuộc LLM):**

```bash
uv run --project .. pytest app/tests/unit/test_anti_bias.py -v
```

**Kỳ vọng**: 5 test pass, bao gồm đúng case plan yêu cầu — `test_diversity_validator_converts_university_only_list_into_mixed_list`.

### 2.4. Xem lại lịch sử đề xuất

```bash
curl "http://127.0.0.1:8000/guidance/students/<demo_student_id>/recommendations"
```

**Kỳ vọng**: tất cả recommendation đã sinh ra ở 2.2 (gọi nhiều lần sẽ cộng dồn — mỗi lần sinh là một sự kiện tư vấn mới, không ghi đè).

### Checklist Dev 3

- [ ] Mỗi recommendation có `reasoning_explanation` không rỗng (yêu cầu explainability bắt buộc)
- [ ] `path_id` luôn nằm trong catalog đã seed (AI không tự bịa path)
- [ ] `pytest app/tests/unit/test_anti_bias.py` pass toàn bộ
- [ ] Không có recommendation nào diễn đạt như một chỉ định bắt buộc (đọc qua `reasoning_explanation`, phải ở dạng tham khảo)

---

## Phần 3 — Luồng kết hợp Dev 1 → Dev 3 (end-to-end)

1. `POST /market/seed-demo-data`
2. `POST /guidance/seed-demo-data`
3. `POST /guidance/students/{demo_student_id}/recommendations?count=3`
4. Đối chiếu `reasoning_explanation` với `GET /market/careers/` — nội dung giải thích phải phản ánh đúng `market_trend` thật tại thời điểm gọi (vd. nếu "Backend Developer" đang `RISING`, path liên quan tới ngành đó nên được ưu tiên nhắc tới xu hướng tăng trưởng trong lý do đề xuất).

Đây là bằng chứng cho thấy dữ liệu thị trường (Dev 1) thực sự chảy vào quyết định tư vấn (Dev 3), không phải hai domain độc lập.
