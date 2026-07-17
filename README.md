# Career Guidance System

Backend cho hệ thống định hướng nghề nghiệp: phân tích tín hiệu kỹ năng từ dữ liệu tuyển dụng thực tế (lương, xu hướng theo vùng miền, thay đổi theo thời gian), xây dựng hồ sơ năng lực học sinh/sinh viên qua tương tác, và đề xuất lộ trình học tập/nghề nghiệp cá nhân hóa, có thể giải thích, chống thiên kiến giới/vùng miền.

Chi tiết kiến trúc, design pattern, và roadmap từng sprint xem tại [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Trạng thái hiện tại

| Domain | Models | Router (API) | Ghi chú |
| :--- | :--- | :--- | :--- |
| `market` (Dev 1) | ✅ | ✅ đã mount vào `main.py` | Ingestion, skill demand, skill trend, auto-update `market_trend` |
| `student` (Dev 2) | ✅ | ❌ chưa có | Chỉ có model + repository, chưa có service/router |
| `guidance` (Dev 3) | ✅ | ❌ chưa có | Chỉ có model + repository, chưa có service/router/anti-bias |

Chỉ domain `market` hiện gọi được qua API. Bảng của `student`/`guidance` vẫn được tạo trong DB (model được import trong `main.py`) để không phá vỡ foreign key khi hai domain kia được nối dây ở các sprint sau.

## Kiến trúc

Domain-Driven Design + Layered Architecture (Router → Service → Repository → Model), mỗi domain nằm độc lập dưới `app/domains/`:

```
app/
├── main.py              # Entry point: khởi tạo FastAPI, include_router, tạo bảng
├── core/                # config (Pydantic Settings), database (engine/session/Base), security (JWT), exceptions
├── domains/
│   ├── market/          # Dev 1 — Skill, Career, JobPosting, JobSkill, CareerSkill
│   ├── student/         # Dev 2 — Student, InteractionLog, StudentSkillAssociation
│   └── guidance/        # Dev 3 — EducationPath, Recommendation
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

`DATABASE_URL` là bắt buộc (không có giá trị mặc định). Các biến khác (`PROJECT_NAME`, `VERSION`, `ENABLE_SEED_ENDPOINT`) đã có default trong `app/core/config.py`, chỉ cần override khi cần.

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

## Test Swagger / thử API

Sau khi server chạy ở `http://127.0.0.1:8000`:

- **Swagger UI**: http://127.0.0.1:8000/docs — interactive, có nút "Try it out" gọi thẳng API, nhóm theo tag `Market Data` / `Student Profile` / `AI Guidance`.
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

`app/tests/unit` và `app/tests/integration` hiện là scaffold rỗng — sẽ được lấp đầy theo Test Plan trong `IMPLEMENTATION_PLAN.md` (unit cho `service.py`/`anti_bias.py`, integration cho luồng router → service → DB).

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
