# Data Model — Market (Labor Market Signals)

Cấu trúc dữ liệu 4 cấp của domain `market`, phục vụ dashboard "Phân tích xu hướng kỹ năng" và tín hiệu thị trường lao động ([requirements.md §24](requirements.md#24-labor-market-requirements)). Xem [ARCHITECTURE.md](ARCHITECTURE.md) cho bức tranh domain tổng thể, [DATA_MODEL.md](DATA_MODEL.md) cho `task`/`evidence`/`eportfolio`.

## 1. Phân cấp

```
Career (ngành, vd. "Công nghệ thông tin")
  └─ Job (nghề cụ thể, vd. "DevOps", "Backend Developer", "MLOps")
       └─ JobPosting (1 tin tuyển dụng cụ thể, đơn trị seniority_level)
```

`Job` cố ý trùng tiền tố với `JobPosting` — phân biệt khi đọc code: **`Job`** = nghề/nhóm-nghề (catalog được curate, giống `Career`/`Skill`), **`JobPosting`** = 1 tin tuyển dụng cụ thể (instance, đến từ ingest qua `POST /market/jobs/bulk`).

`Skill` là **1 entity duy nhất, dùng chung** cho cả 2 cấp liên kết:
- `JobSkill` (job_id, skill_id) — skill đặc thù của 1 nghề cụ thể, dùng để **tính `market_trend`**.
- `CareerSkill` (career_id, skill_id) — skill nền tảng/chung của cả ngành (Toán học, Tư duy logic...), **không** dùng tính trend — chỉ là fallback classification khi 1 posting không đủ tín hiệu để gán vào `Job` cụ thể (case beginner/entry-level).

Cùng 1 skill (vd. "SQL") có thể vừa gắn cho 1 `Job` cụ thể vừa gắn cho `Career` chung — không xung đột.

`JobPostingSkill` (job_posting_id, skill_id) là bảng khác hẳn `JobSkill` — đây là skill **1 posting cụ thể yêu cầu** (đến từ ingest), không phải skill định nghĩa catalog.

## 2. Entities

### `Skill`
`name` (unique), `category`, `description`.

### `Career` — ngành chung nhất
`title` (unique, vd. "Công nghệ thông tin"), `description`, `market_trend` (**rollup** từ union skill-set của toàn bộ `Job` con — không tính trực tiếp). Quan hệ: `jobs` (1-N), `general_skills` (N-N qua `CareerSkill`).

### `Job` — nghề cụ thể trong 1 ngành
`title` (unique, vd. "DevOps"), `description`, `career_id` (FK), `market_trend` (tính trực tiếp từ `JobSkill` — 2-cửa-sổ 30 ngày, growth ≥ +15% → `RISING`, ≤ -15% → `DECLINING`, còn lại `STABLE`). Quan hệ: `career`, `skills` (N-N qua `JobSkill`).

### `JobPosting` — 1 tin tuyển dụng
| field | ghi chú |
|---|---|
| title, company, location, description | |
| requirements, benefits | nullable |
| salary_min / salary_max | nullable — không phải mọi tin đều công khai lương |
| posted_at | indexed — mọi query trend/demand filter theo range này; nhận từ client để backfill dữ liệu lịch sử thật, không mặc định "now" |
| job_id | Optional FK → `Job.id` — null khi không khớp được nghề cụ thể nào |
| career_id | Optional FK → `Career.id` — **denormalized, độc lập với `job_id`**: khi khớp được `Job` thì `career_id = job.career_id`; khi KHÔNG khớp `Job` nào nhưng khớp được `CareerSkill` (case beginner, chỉ có skill chung chung), `career_id` vẫn được gán trong khi `job_id` để trống |
| seniority_level | Optional enum `SeniorityLevel` (INTERN/JUNIOR/MID/SENIOR/MANAGER) — **đơn trị mỗi dòng**. Một tin gốc bao nhiều cấp bậc (vd. "Junior/Mid") được **service tự tách thành nhiều `JobPosting` riêng** lúc ingest, không lưu đa trị trên 1 dòng |

### Bảng liên kết N-N
`JobSkill` (job_id, skill_id), `CareerSkill` (career_id, skill_id), `JobPostingSkill` (job_posting_id, skill_id) — 3 bảng, mục đích khác nhau như mục 1.

## 3. Heuristic gán `job_id`/`career_id`/`seniority_level` lúc ingest

Tất định, không gọi AI (bulk ingest có thể hàng trăm dòng/lần):

1. **`_resolve_job_id`**: `Job` có nhiều skill trùng nhất với posting (ngưỡng tối thiểu 1 skill trùng); `None` nếu không đủ tín hiệu.
2. **`_resolve_career_id_fallback`** — chỉ chạy khi (1) trả `None`: khớp theo `CareerSkill` (skill chung chung) → gán được `career_id` dù không xác định `Job` cụ thể. Nếu cả 2 tầng đều không khớp, posting vẫn được lưu với `job_id`/`career_id` đều `null` (không chặn ingest).
3. **`_infer_seniority_levels`**: keyword-matching trên `title` (rẻ tiền, không gọi AI), mặc định `[MID]` nếu không khớp từ khoá nào. Client có thể truyền `seniority_levels` tường minh để override.

Giá trị client truyền tường minh (`job_id`/`career_id`/`seniority_levels`) luôn được ưu tiên, giống cách `posted_at` đã hoạt động.

## 4. Market Signal — yêu cầu bắt buộc

Mỗi tín hiệu thị trường trả về phải có nguồn/độ tin cậy ([requirements.md §24](requirements.md#24-labor-market-requirements)):

```json
{
  "sources": [],
  "sample_size": 0,
  "period": "",
  "updated_at": "",
  "confidence": "",
  "limitations": []
}
```

Hiện tại `MarketOverviewRead.stats.confidence` (bucket theo `sample_size` — `HIGH`/`MEDIUM`/`LOW`, ngưỡng ở `CONFIDENCE_SAMPLE_THRESHOLDS`) là phần đã implement của yêu cầu này; các field còn lại (`sources`, `limitations` tường minh) chưa có ở mọi response — cân nhắc bổ sung nếu cần đúng 100% shape spec.

§24 cũng liệt kê "salary range" và "entry-level opportunities" là 2 output bắt buộc — implement ở `MarketOverviewRead`:
- **`salary_groups`** (top-level, ngang hàng `location_distribution`): `MarketRepository.get_salary_by_job_group` — `AVG(salary_min)`/`AVG(salary_max)`/`COUNT(*)` group theo `Job.title` (unwindowed, giống `location_distribution` — không filter theo `days`). Job không có posting nào có `job_id` resolve được (case beginner-fallback chỉ có `career_id`) không xuất hiện ở đây.
- **`stats.entry_level_ratio_percent`**: % posting trong cửa sổ `days` hiện tại (cùng window với `total_job_postings`) có `seniority_level` là `INTERN`/`JUNIOR` (`ENTRY_LEVEL_SENIORITIES` ở `market/repository.py` — **giả định**, spec không định nghĩa chính xác "entry-level" gồm những level nào). `null` khi cửa sổ hiện tại không có posting nào, không giả `0%`.

## 5. Endpoint chính (`domains/market/router.py`)

| Endpoint | Việc |
|---|---|
| `POST /market/jobs/bulk` | Bulk ingest `JobPosting`, tự trigger `update_market_trends` ở background sau khi ingest |
| `GET /market/overview` | Dashboard tổng hợp: stat card, chart tuần, phân bố khu vực. Filter: `days`, `location`, `career_id`, `seniority[]`, `salary_min/max` |
| `GET /market/careers/{career_id}/jobs` | Drill-down demand/growth theo từng `Job` trong 1 `Career` |
| `GET /market/analytics/skill-demand` / `skill-trend` | Tín hiệu theo skill, có/không filter `location` |
| `GET /market/careers/`, `/market/jobs/` | List catalog, filter theo `trend` |

## 6. Ghi chú tích hợp với `guidance`

`domains/guidance/service.py` gọi `market_repo.get_careers()` và dùng trực tiếp `c.title`/`c.market_trend.value` để build prompt AI gợi ý ngành học — **không đổi shape/tên method này** nếu sửa domain `market`, chỉ ý nghĩa dữ liệu thay đổi (Career giờ là "ngành" thay vì "nghề cụ thể", ít Career hơn — khớp tốt hơn với `EducationPath` vốn cũng ở mức ngành rộng).
