# Career Guidance System

Backend cho hệ thống định hướng nghề nghiệp: phân tích tín hiệu kỹ năng từ dữ liệu tuyển dụng thực tế (lương, xu hướng theo vùng miền, thay đổi theo thời gian), xây dựng hồ sơ năng lực học sinh/sinh viên qua tương tác, và đề xuất lộ trình học tập/nghề nghiệp cá nhân hóa, có thể giải thích, chống thiên kiến giới/vùng miền.

Chi tiết kiến trúc, design pattern, và roadmap từng sprint xem tại [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Trạng thái hiện tại

| Domain | Models | Router (API) | Ghi chú |
| :--- | :--- | :--- | :--- |
| `market` (Dev 1) | ✅ | ✅ đã mount vào `main.py` | Ingestion, skill demand, skill trend, auto-update `market_trend` |
| `student` (Dev 2) | ✅ | ❌ chưa có | Chỉ có model + repository, chưa có service/router riêng — `guidance` seed tạm tạo 1 demo student qua repository có sẵn |
| `guidance` (Dev 3) | ✅ | ✅ đã mount vào `main.py` | Recommendation engine + `AntiBiasEngine` (Strategy Pattern) |
| `chatbot` | — (stateless) | ✅ đã mount vào `main.py` | Proxy tới FPT Cloud chat-completions API; không có bảng DB |

`student` chưa có router riêng (chưa đến lượt theo roadmap Sprint), nhưng bảng của nó đã tồn tại và `guidance` đọc/ghi trực tiếp qua `StudentRepository` có sẵn.

## Kiến trúc

Domain-Driven Design + Layered Architecture (Router → Service → Repository → Model), mỗi domain nằm độc lập dưới `app/domains/`:

```
app/
├── main.py              # Entry point: khởi tạo FastAPI, include_router, tạo bảng
├── core/                # config (Pydantic Settings), database (engine/session/Base), security (JWT), exceptions
├── domains/
│   ├── market/          # Dev 1 — Skill, Career, JobPosting, JobSkill, CareerSkill
│   ├── student/         # Dev 2 — Student, InteractionLog, StudentSkillAssociation
│   ├── guidance/        # Dev 3 — EducationPath, Recommendation
│   └── chatbot/         # Stateless proxy to an external LLM chat API (no models.py)
└── tests/                # unit/ + integration/ (scaffold, chưa có test)
```

**Lưu ý quan trọng**: mọi import trong domain đều là absolute, không có prefix `app.` (ví dụ `from core.database import Base`). Vì vậy `app/` phải là working directory khi chạy server — xem hướng dẫn chạy bên dưới.

## Yêu cầu môi trường

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) để quản lý dependency (thay cho pip/requirements.txt)
- PostgreSQL (đang dùng Neon serverless Postgres cho môi trường dev/demo)

## Cài đặt

```bash
# Cài uv nếu chưa có (Windows PowerShell)
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Cài dependency theo uv.lock (tạo .venv tự động)
uv sync
```

### Cấu hình biến môi trường

Copy file mẫu và điền giá trị thật — **file `.env` phải nằm trong `app/`**, không phải ở repo root (vì server chạy với cwd = `app/`):

```bash
cp app/.env.example app/.env
```

Sửa `app/.env`:

```
DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require"
```

`DATABASE_URL` là bắt buộc (không có giá trị mặc định). Các biến khác (`PROJECT_NAME`, `VERSION`, `ENABLE_SEED_ENDPOINT`, `FPT_CLOUD_API_KEY`, `FPT_CLOUD_BASE_URL`, `FPT_CLOUD_CHAT_MODEL`) đã có default trong `app/core/config.py`, chỉ cần override khi cần. `FPT_CLOUD_API_KEY` để trống thì phần còn lại của app vẫn chạy bình thường — chỉ `/assistant/chat` trả 503 và `/assistant/health` báo `configured: false`.

## Chạy server (local dev)

```bash
cd app
uv run --project .. uvicorn main:app --reload --port 8000
```

- `cd app` trước vì import trong code giả định `app/` là root (`core.database`, `domains.market...`).
- `--project ..` trỏ `uv` về `pyproject.toml`/`uv.lock` ở repo root.
- `--reload` để auto-restart khi sửa code (chỉ dùng cho dev, bỏ khi chạy production).

Lần chạy đầu tiên, `Base.metadata.create_all()` trong `main.py` sẽ tự tạo toàn bộ bảng (kể cả của `student`/`guidance`) trên database chỉ định trong `DATABASE_URL`.

## Seed dữ liệu mẫu

```
POST /market/seed-demo-data
```

Tạo sẵn 10 skill, 5 career (Backend/Frontend/Data Scientist/DevOps/Business Analyst) và 35 job posting trải trên 5 thành phố (Hồ Chí Minh, Hà Nội, Đà Nẵng, Cần Thơ) với `posted_at` rải trong 60 ngày gần đây, rồi tự trigger `update_market_trends` ngay lập tức — gọi xong là có đủ dữ liệu để thấy `RISING`/`DECLINING`/`STABLE` thật trên `GET /market/careers/` và chênh lệch nhu cầu kỹ năng theo vùng (ví dụ Đà Nẵng gần như không có tin nào cần Docker/Kubernetes/AWS/Machine Learning — mô phỏng "thiếu hụt kỹ năng tại địa phương").

- Idempotent với skill/career (match theo tên, gọi lại không tạo trùng); job posting thì được thêm mới mỗi lần gọi.
- Bị tắt khi biến môi trường `ENABLE_SEED_ENDPOINT=false` — **luôn set false khi deploy production**, vì đây là endpoint không có auth, có thể bị lạm dụng để ghi rác vào DB nếu để public.

## Chatbot AI

Proxy tới FPT Cloud Marketplace chat-completions API (OpenAI-compatible). Không lưu hội thoại vào DB — client tự giữ `history` và gửi lại mỗi lần gọi.

```
POST /assistant/chat
{
  "message": "Em thích vẽ và làm việc với máy tính, nên học ngành gì?",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```
→ `{"reply": "...", "model": "gemma-4-31B-it"}`

System prompt cố định server-side (không nhận từ client) để không ai override hành vi/guardrail của assistant qua request body.

```
GET /assistant/health          # chỉ kiểm tra FPT_CLOUD_API_KEY có được set không — nhanh, miễn phí
GET /assistant/health?deep=true  # gọi thật lên FPT Cloud (1 request tối thiểu) để xác nhận kết nối — tốn quota/độ trễ, không nên dùng cho health probe tần suất cao
```

## AI Guidance (đề xuất lộ trình học tập)

Kết hợp hồ sơ học sinh (Dev 2), xu hướng thị trường (Dev 1), và một catalog `EducationPath` đã có sẵn, để LLM chọn ra lộ trình phù hợp kèm giải thích — rồi chạy qua `AntiBiasEngine` trước khi lưu.

```
POST /guidance/seed-demo-data     # 6 education path (đủ 3 loại hình, có cả remote) + 1 demo student (Cần Thơ)
POST /guidance/education-paths/   # tự thêm path khác nếu muốn
GET  /guidance/education-paths/

POST /guidance/students/{student_id}/recommendations?count=3
GET  /guidance/students/{student_id}/recommendations
```

Pipeline của `POST .../recommendations`:
1. Lấy `Student.ai_inferred_profile` + `current_location` (Dev 2) và toàn bộ `Career.market_trend` hiện có (Dev 1).
2. Gọi LLM (dùng chung `ChatbotService.complete()` với domain `chatbot`, nhưng system prompt khác hẳn — yêu cầu chọn đúng từ catalog theo `path_id`, trả JSON, không được dựa vào giới tính/quê quán) để sinh `reasoning_explanation` cho từng lựa chọn.
3. **`AntiBiasEngine`** (Strategy Pattern, `domains/guidance/anti_bias.py`):
   - `DiversityValidator` — nếu tất cả gợi ý cùng một `PathType` (vd. toàn `UNIVERSITY`), thay 1 slot bằng loại hình khác từ catalog.
   - `RegionExpansionValidator` — nếu tất cả gợi ý đều gắn với đúng `current_location` của học sinh, thay 1 slot bằng path `location=None` (remote/toàn quốc).
   - Cả hai đều gắn `reasoning_explanation` riêng giải thích lý do được bổ sung — không âm thầm chèn.
4. Lưu các recommendation đã qua validate vào DB, trả về kèm `reasoning_explanation`.

Unit test cho đúng case plan yêu cầu ("DiversityValidator converts a University-only list into a mixed list") nằm ở `app/tests/unit/test_anti_bias.py`.

## Test Swagger / thử API

Sau khi server chạy ở `http://127.0.0.1:8000`:

- **Swagger UI**: http://127.0.0.1:8000/docs — interactive, có nút "Try it out" gọi thẳng API, nhóm theo tag `Market Data` / `Student Profile` / `AI Guidance` / `AI Chatbot` / `Dev Tools`.
- **ReDoc**: http://127.0.0.1:8000/redoc — bản đọc tài liệu tĩnh.
- **OpenAPI JSON**: http://127.0.0.1:8000/openapi.json — import vào Postman/Insomnia nếu cần.

Cách nhanh nhất: gọi `POST /market/seed-demo-data` (mục trên) một lần rồi thử thẳng các endpoint `GET` bên dưới. Hoặc tự tạo dữ liệu thủ công theo luồng sau (qua `/docs`):

1. `POST /market/skills/` — tạo một vài skill (ví dụ "Python", "React").
2. `POST /market/careers/` — tạo career, truyền `skill_ids` của các skill vừa tạo để nối tín hiệu thị trường vào career này.
3. `POST /market/jobs/bulk` — nạp một danh sách job posting (có `location`, `salary_min/max`, `skill_ids`, tùy chọn `posted_at` để nạp dữ liệu lịch sử). Endpoint này tự trigger tính lại `market_trend` ở background sau khi ingest.
4. `GET /market/analytics/skill-demand?location=...` — xem tần suất kỹ năng theo khu vực.
5. `GET /market/analytics/skill-trend?location=...&window_days=30` — xem tăng/giảm nhu cầu kỹ năng giữa hai khung thời gian liên tiếp.
6. `GET /market/careers/?trend=RISING` — lọc career theo xu hướng vừa được tính.

## Chạy test (pytest)

```bash
uv run --project .. pytest
```

`app/tests/unit/test_anti_bias.py` có sẵn; `app/tests/integration` vẫn là scaffold rỗng — sẽ lấp đầy theo Test Plan trong `IMPLEMENTATION_PLAN.md` (integration cho luồng router → service → DB). `pythonpath = ["app"]` đã cấu hình trong `pyproject.toml` nên chạy `pytest` từ đâu cũng import được `core.*`/`domains.*`.

## Docker / Deploy lên Cloud Run

```bash
docker build -t career-guidance .
docker run -p 8080:8080 -e DATABASE_URL="postgresql://..." career-guidance
```

- Image build bằng `uv sync --frozen --no-dev` từ `uv.lock` — không dùng `pip`/`requirements.txt`.
- `.env` **không** được copy vào image (loại trừ qua `.dockerignore`). Trên Cloud Run, truyền secret qua `--set-env-vars` hoặc (khuyến nghị) `--set-secrets` bằng Secret Manager, không dùng file `.env`.
- Container lắng nghe theo biến `$PORT` mà Cloud Run tiêm vào lúc runtime (mặc định 8080).

```bash
gcloud run deploy career-guidance \
  --source . \
  --region asia-southeast1 \
  --set-secrets DATABASE_URL=career-guidance-db-url:latest \
  --allow-unauthenticated
```

## Ràng buộc đạo đức (bắt buộc với domain `guidance`)

Khi triển khai Sprint 3 cho `domains/guidance`: mọi đề xuất phải mở rộng lựa chọn thay vì đóng khung người dùng, không củng cố định kiến giới/vùng miền, và phải kèm `reasoning_explanation` để học sinh/sinh viên tự quyết định dựa trên tham khảo — không phải chỉ định. Xem `AntiBiasEngine` (Strategy Pattern) trong mục 2 và 4 của `IMPLEMENTATION_PLAN.md`.
