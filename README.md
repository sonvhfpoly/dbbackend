# WORKLAB / Career Guidance Backend

Backend cho nền tảng kết nối doanh nghiệp — giáo viên/mentor — sinh viên qua các nhiệm vụ nghề nghiệp thực tế: phân tích tín hiệu kỹ năng từ dữ liệu tuyển dụng thực tế, xây dựng hồ sơ năng lực sinh viên qua tương tác và task thực hành, và đề xuất lộ trình học tập/nghề nghiệp cá nhân hóa, có thể giải thích, chống thiên kiến giới/vùng miền.

**Docs:**
- [requirements.md](docs/requirements.md) — spec sản phẩm đầy đủ (source of truth cho business rules)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — kiến trúc, design pattern, bản đồ domain, quyết định không-có-auth
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — entity của `task`/`evidence`/`eportfolio`
- [docs/MARKET_DATA_MODEL.md](docs/MARKET_DATA_MODEL.md) — entity của `market` (Career/Job/JobPosting)
- [docs/TESTING.md](docs/TESTING.md) — hướng dẫn chạy, test, tích hợp end-to-end toàn bộ domain
- [docs/CODE_REVIEW_ASSIGNMENTS.md](docs/CODE_REVIEW_ASSIGNMENTS.md) — phân công review code cho 3 dev, chia theo domain

## Trạng thái hiện tại

| Domain | Vai trò | Ghi chú |
|---|---|---|
| `market` | Skill/Career/Job/JobPosting catalog, market trend, dashboard overview | Ingestion, skill demand/trend, dashboard `/market/overview` |
| `student` | Student profile, skill leveling, career recommendation | `StudentSkillProfile`/`StudentSkillEvent`, rule-based recommendation |
| `guidance` | EducationPath + Recommendation | `AntiBiasEngine` (Strategy Pattern) — diversity + region expansion |
| `chatbot` | Proxy LLM chat-completions | Stateless, không có bảng DB |
| `task` | Task marketplace: company task, sub-task, review (T/R-level), submission workflow | Đầy đủ state machine + `TaskReview` (approve/reject task trước khi student join được) |
| `task_builder` | AI Task Builder — brief doanh nghiệp → Task có cấu trúc | Hội thoại nhiều lượt, tạo Task qua `TaskService.create_task(skip_ai_planning=True)` |
| `evidence` | EvidenceClaim: AI draft → student review → mentor verify | Chỉ `VERIFIED` mới cập nhật `StudentSkillProfile` |
| `eportfolio` | Tổng hợp view student/business + share consent | Không cache — tổng hợp real-time mỗi lần gọi |

Mọi domain đã mount vào `main.py`. Schema version hóa bằng Alembic (`app/alembic/`), có fallback `AUTO_CREATE_SCHEMA` cho dev/demo — xem [docs/ARCHITECTURE.md §4](docs/ARCHITECTURE.md#4-schema--migration-alembic).

**Không có Auth/RBAC** — quyết định có chủ đích để đơn giản hóa test/demo, xem [docs/ARCHITECTURE.md §3](docs/ARCHITECTURE.md#3-không-có-authrbac--quyết-định-có-chủ-đích).

## Kiến trúc (tóm tắt)

Domain-Driven Design + Layered Architecture (Router → Service → Repository → Model), mỗi domain độc lập dưới `app/domains/`. Chi tiết đầy đủ ở [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
app/
├── main.py              # Entry point: FastAPI init, include_router mọi domain, AUTO_CREATE_SCHEMA
├── core/                 # config (Pydantic Settings), database (engine/session/Base), security, exceptions
├── alembic/               # Migration versioned (alembic.ini ở app/alembic.ini)
├── domains/
│   ├── market/           # Skill, Career, Job, JobPosting
│   ├── student/          # Student, StudentProfile, StudentSkillProfile/Event
│   ├── guidance/         # EducationPath, Recommendation
│   ├── chatbot/          # Stateless proxy tới LLM chat API
│   ├── task/             # Company, Task, TaskReview, TaskSubmission, TaskSubmissionFile
│   ├── task_builder/     # AI Task Builder
│   ├── evidence/         # EvidenceClaim
│   └── eportfolio/       # Aggregation view + share consent
└── tests/unit/            # Pure-logic test, không cần DB thật
```

**Lưu ý quan trọng**: mọi import trong domain đều là absolute, không có prefix `app.` (ví dụ `from core.database import Base`). Vì vậy `app/` phải là working directory khi chạy server/alembic/pytest.

## Yêu cầu môi trường

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) để quản lý dependency
- PostgreSQL (đang dùng Neon serverless Postgres cho môi trường dev/demo)

## Cài đặt

```bash
# Cài uv nếu chưa có (Windows PowerShell)
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Cài dependency theo uv.lock (tạo .venv tự động)
uv sync
```

### Cấu hình biến môi trường

Copy file mẫu và điền giá trị thật — **file `.env` phải nằm trong `app/`**, không phải ở repo root:

```bash
cp app/.env.example app/.env
```

Sửa `app/.env`:

```
DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require"
```

`DATABASE_URL` là bắt buộc (không có default). Các biến khác đã có default hợp lý trong `app/core/config.py`:

| Biến | Default | Ghi chú |
|---|---|---|
| `ENABLE_SEED_ENDPOINT` | `true` | Bật `POST .../seed-demo-data` ở mọi domain — set `false` ở production |
| `AUTO_CREATE_SCHEMA` | `true` | Tự tạo bảng còn thiếu lúc startup (dev/demo convenience) — set `false` ở production, dùng `alembic upgrade head` |
| `FPT_CLOUD_API_KEY` | (trống) | Để trống thì app vẫn chạy, chỉ endpoint AI trả `503` |
| `VERTEX_PROJECT_ID` | (trống, auto-detect) | Vertex AI được ưu tiên hơn FPT Cloud khi ADC khả dụng |
| `TASK_BUILDER_GCS_BUCKET` | (trống) | Cần cho upload tài liệu ở `task_builder`; bỏ trống thì endpoint đó trả `503` |

## Chạy server (local dev)

```bash
cd app
uv run --project .. uvicorn main:app --reload --port 8000
```

- `cd app` trước vì import trong code giả định `app/` là root.
- `--project ..` trỏ `uv` về `pyproject.toml`/`uv.lock` ở repo root.
- Lần chạy đầu tiên, `AUTO_CREATE_SCHEMA=true` tự tạo toàn bộ bảng (mọi domain) trên DB chỉ định ở `DATABASE_URL` — không cần chạy migration tay.

## Test API qua Swagger

Sau khi server chạy ở `http://127.0.0.1:8000`:

- **Swagger UI**: http://127.0.0.1:8000/docs — nhóm theo tag của từng domain, có nút "Try it out".
- **ReDoc**: http://127.0.0.1:8000/redoc
- **OpenAPI JSON**: http://127.0.0.1:8000/openapi.json — import vào Postman/Insomnia.

Cách nhanh nhất: gọi `POST /market/seed-demo-data`, `POST /guidance/seed-demo-data`, `POST /tasks/seed-demo-data` rồi thử các endpoint `GET`. Hướng dẫn chi tiết từng luồng (kèm end-to-end tích hợp xuyên domain) ở **[docs/TESTING.md](docs/TESTING.md)**.

## Chạy test (pytest)

```bash
uv run --project .. pytest -q
```

`pythonpath = ["app"]` đã cấu hình trong `pyproject.toml` nên chạy `pytest` từ đâu cũng import được `core.*`/`domains.*`. Chi tiết từng file test ở [docs/TESTING.md §1](docs/TESTING.md#1-chạy-test-tự-động-pytest-không-cần-dbai-thật).

## Migration (Alembic)

```bash
cd app
alembic upgrade head              # áp dụng migration mới nhất
alembic revision --autogenerate -m "mo ta"   # tạo migration mới sau khi sửa models.py
```

Xem [docs/TESTING.md §8](docs/TESTING.md#8-alembic--migration) để biết cách xử lý một DB đã có sẵn schema từ `create_all()` cũ (`alembic stamp head`).

## Docker / Deploy lên Cloud Run

```bash
docker build -t career-guidance .
docker run -p 8080:8080 -e DATABASE_URL="postgresql://..." career-guidance
```

- Image build bằng `uv sync --frozen --no-dev` — không dùng `pip`/`requirements.txt`.
- `.env` **không** được copy vào image (loại trừ qua `.dockerignore`). Trên Cloud Run, dùng `--set-secrets` (Secret Manager), không dùng file `.env`.
- Container lắng nghe biến `$PORT` Cloud Run tiêm vào lúc runtime.
- **Set `ENABLE_SEED_ENDPOINT=false` và `AUTO_CREATE_SCHEMA=false` khi deploy production.**

```bash
gcloud run deploy career-guidance \
  --source . \
  --region asia-southeast1 \
  --set-secrets DATABASE_URL=career-guidance-db-url:latest \
  --allow-unauthenticated
```

## Ràng buộc đạo đức (bắt buộc với domain `guidance`)

Mọi đề xuất phải mở rộng lựa chọn thay vì đóng khung người dùng, không củng cố định kiến giới/vùng miền, và phải kèm `reasoning_explanation` để học sinh/sinh viên tự quyết định dựa trên tham khảo — không phải chỉ định. Xem `AntiBiasEngine` (Strategy Pattern) trong [docs/ARCHITECTURE.md §6](docs/ARCHITECTURE.md#6-ràng-buộc-đạo-đức-bắt-buộc-với-domain-guidance).
