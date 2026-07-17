# Plan: Mở rộng domain `market` để phục vụ trang Dashboard "Phân Tích Xu Hướng Kỹ Năng"

## Context

Trang dashboard mới (persona "Market Analyst") gồm: 5 bộ lọc (khoảng thời gian, khu vực, ngành nghề, cấp bậc, mức lương), 4 stat card (tổng tin tuyển dụng + tăng trưởng MoM, số nhóm nghề, số kỹ năng phân tích, tốc độ tăng trưởng), 1 biểu đồ xu hướng tuyển dụng theo tuần (kèm đường trung bình năm), và 1 panel phân bố khu vực (top khu vực + % + "khu vực khác"). Phần dưới màn hình bị cắt (không phân tích được).

Domain `market` hiện tại (`app/domains/market/`) có `Skill`, `Career` (N-N với Skill qua `CareerSkill`, hiện đang đóng vai trò "nhóm nghề" như "Backend Developer"/"DevOps Engineer"), `JobPosting` (N-N với Skill qua `JobSkill`, `location` string tự do, `salary_min/max`, `posted_at`, không liên kết trực tiếp tới `Career`).

Bản plan đã qua **4 vòng chỉnh sửa theo phản hồi**:
1. **Vòng 1**: đề xuất ban đầu (`Career.industry: str` + group theo raw `JobPosting.title`) bị bác — phân cấp đúng phải là: `Career` = ngành chung nhất (vd. "Công nghệ thông tin"), còn "job" = nghề cụ thể (DevOps, MLOps, Software Dev...) cần 1 entity riêng ở giữa `Career` và `JobPosting`; đồng thời cấp bậc tuyển dụng (`seniority`) cần đa trị.
2. **Vòng 2**: đề xuất entity mới tên `Role` + lưu `seniority_levels` dạng mảng (Postgres ARRAY) bị bác — chốt lại: **đặt tên entity là `Job`**; **level là đơn trị** trên mỗi `JobPosting` — khi 1 tin gốc thực sự bao nhiều cấp bậc (vd. "Junior/Mid"), hệ thống **tách thành nhiều `JobPosting` riêng** (mỗi dòng 1 cấp bậc); việc lọc/thống kê theo nhiều cấp bậc cùng lúc do **tầng service tự gộp** (query `IN (...)`). `JobPosting` cũng cần thêm chi tiết yêu cầu/phúc lợi.
3. **Vòng 3**: case beginner — 1 posting chưa đủ tín hiệu (skill) để gán vào 1 `Job` cụ thể (vd. chỉ ghi "toán học", "giải quyết vấn đề", "tư duy logic"), cần skill **gắn ở cấp `Career` (ngành) chung chung hơn** làm phương án dự phòng khi không khớp được `Job` nào. Cả 2 loại skill (đặc thù 1 nghề, và chung chung cho cả ngành) đều dùng chung 1 entity `Skill` duy nhất — `Job` và `Career` mỗi bên có 1 bảng liên kết N-N riêng trỏ về `Skill`.
4. **Vòng 4**: đổi tên bảng liên kết cho gọn — `CareerGeneralSkill` → `CareerSkill`, và bảng liên kết mới của `Job` (trước đặt tên `JobRequiredSkill`) → `JobSkill`. Vì tên `JobSkill` đã được dùng cho bảng liên kết `JobPosting`↔`Skill` có sẵn trong code gốc, bảng đó được đổi tên thành `JobPostingSkill` để tránh trùng.

## Ảnh hưởng liên-domain cần xử lý cùng lúc

`domains/guidance/service.py:59,121` gọi `market_repo.get_careers()` và dùng trực tiếp `c.title`/`c.market_trend.value` để build prompt gợi ý ngành học cho AI (`"- {title}: {trend}"`). Đổi ý nghĩa `Career` thành "ngành chung nhất" **không đổi shape/tên method `get_careers()`/field `market_trend`** — chỉ đổi ý nghĩa dữ liệu (ít Career hơn, mỗi Career giờ là 1 ngành, không phải 1 nghề cụ thể). Không cần sửa `guidance/service.py`; granularity "ngành" còn khớp tốt hơn với `EducationPath` (vốn cũng ở mức ngành học rộng, không phải nghề cụ thể).

## Cấu trúc dữ liệu mới (4 cấp)

```
Career (ngành, vd. "Công nghệ thông tin")
  └─ Job (nghề cụ thể, vd. "DevOps", "MLOps", "Backend Developer") — entity MỚI
       └─ JobPosting (1 tin tuyển dụng, đơn trị seniority_level, kèm requirements/benefits)
```

`Job` cố ý trùng tiền tố với `JobPosting` đã có sẵn trong code — để phân biệt rõ khi đọc code: **`Job`** = nghề/nhóm-nghề (catalog, tương tự cách `Career`/`Skill` là catalog được curate), **`JobPosting`** = 1 tin tuyển dụng cụ thể (instance, đến từ ingest). Bảng liên kết với `Skill` cũng đổi tên để tránh trùng: **`JobPostingSkill`** (đổi tên từ `JobSkill` gốc) = skill mà 1 `JobPosting` cụ thể yêu cầu (đến từ ingest); **`JobSkill`** (tên mới, thế chỗ) = bộ skill định nghĩa 1 `Job`/nghề (curated, dùng để tính market trend) — giữ đúng phân biệt "curated 1 lần" vs "đến từ ingest" mà bản gốc đã có.

**`Skill` vẫn là 1 entity duy nhất, dùng chung** — không tách riêng "skill chung chung" thành 1 bảng/model khác. `Job` và `Career` mỗi bên có 1 bảng liên kết N-N riêng trỏ về cùng `Skill`: `JobSkill` (job_id, skill_id) cho skill đặc thù của 1 nghề (tính market trend), `CareerSkill` (career_id, skill_id) cho skill nền tảng/chung của cả ngành (fallback cho case beginner) — cùng 1 skill (vd. "SQL") hoàn toàn có thể vừa được gắn cho 1 `Job` cụ thể vừa gắn cho `Career` chung, không có xung đột hay trùng lặp entity.

`market_trend` (RISING/STABLE/DECLINING) chuyển xuống `Job` (nơi có skill-linkage trực tiếp để tính), `Career.market_trend` tính **rollup** từ union skill-set của toàn bộ `Job` con (cùng công thức 2-cửa-sổ/`TREND_GROWTH_THRESHOLD` hiện có, join sâu thêm 1 cấp) — giữ nguyên contract cho `guidance`.

## Thay đổi Schema (`app/domains/market/models.py`)

```python
class SeniorityLevel(enum.Enum):
    INTERN = "INTERN"; JUNIOR = "JUNIOR"; MID = "MID"; SENIOR = "SENIOR"; MANAGER = "MANAGER"
```
(Giả định thang 5 mức — UI chỉ hiện 1 lựa chọn gộp "Junior / Intern" nên không thấy hết danh sách, ghi rõ trong comment.)

**`Job` (entity mới, table `jobs`)**:
```python
class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # "DevOps", "Backend Developer", ...
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id"), index=True)  # ngành mà nghề này thuộc về
    market_trend: Mapped[MarketTrend] = mapped_column(SQLEnum(MarketTrend), default=MarketTrend.STABLE)

    career = relationship("Career", back_populates="jobs")
    skills = relationship("Skill", secondary="job_skills")

class JobSkill(Base):
    """Curated skill set that defines one Job (used to compute its market_trend).
    Distinct from JobPostingSkill, which tags what one ingested JobPosting actually asked for."""
    __tablename__ = "job_skills"
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
```
Thay thế hoàn toàn vai trò cũ của `CareerSkill` gốc (dùng để tính trend) — bảng đó bị xoá; mọi liên kết skill-để-tính-trend giờ nằm ở `JobSkill` (tên mới).

**`Career`** (giữ nguyên bảng, đổi ý nghĩa) — thêm 1 bảng liên kết MỚI, mục đích khác hẳn `JobSkill`: skill **chung chung/nền tảng** của cả ngành (Toán học, Giải quyết vấn đề, Tư duy logic...), dùng làm tín hiệu fallback cho case beginner, KHÔNG dùng để tính `market_trend`:
```python
class Career(Base):
    __tablename__ = "careers"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # "Công nghệ thông tin", ...
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    market_trend: Mapped[MarketTrend] = mapped_column(SQLEnum(MarketTrend), default=MarketTrend.STABLE)  # rollup từ Job con

    jobs = relationship("Job", back_populates="career")
    general_skills = relationship("Skill", secondary="career_skills")

class CareerSkill(Base):
    """Foundational/general skills for a whole Career (e.g. Math, Problem Solving,
    Logical Thinking) — NOT used to compute market_trend (that's JobSkill's job).
    Used only as a fallback classification signal: a beginner-oriented posting
    that lists only generic skills (no job-specific ones) can still be
    attributed to the right Career even though it can't be pinned to one Job."""
    __tablename__ = "career_skills"
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
```

**`JobPosting`**: thêm
```python
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)  # đơn trị: 1 posting = 1 nghề cụ thể
    # Denormalized, độc lập với job_id: khi posting khớp được 1 Job cụ thể thì career_id = job.career_id;
    # khi KHÔNG khớp được Job nào (case beginner, chỉ có skill chung chung) nhưng vẫn khớp được
    # CareerSkill (skill chung), career_id vẫn được gán trong khi job_id để trống — posting vẫn xuất
    # hiện đúng khi lọc theo ngành, chỉ không xuất hiện ở phần drill-down theo Job cụ thể.
    career_id: Mapped[Optional[int]] = mapped_column(ForeignKey("careers.id"), nullable=True, index=True)
    seniority_level: Mapped[Optional[SeniorityLevel]] = mapped_column(SQLEnum(SeniorityLevel), nullable=True, index=True)  # đơn trị
    requirements: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    benefits: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    job = relationship("Job")
    career = relationship("Career")
```
Bảng liên kết `JobPosting`↔`Skill` gốc (`JobSkill`, cột `job_id` trỏ `job_postings.id`) đổi tên thành **`JobPostingSkill`** (cột đổi thành `job_posting_id`) để không trùng với `Job`↔`Skill` `JobSkill` mới ở trên.

**Xử lý tin gốc đa cấp bậc ("Junior/Mid")**: KHÔNG lưu đa trị trên 1 dòng. `JobPostingCreate` (schema, không phải model) nhận `seniority_levels: List[SeniorityLevel] = []` làm tiện ích đầu vào; ở `ingest_jobs`, nếu list này có >1 phần tử, **service tự tách thành N dòng `JobPosting` riêng** (giống hệt nhau, chỉ khác `seniority_level`) trước khi insert. Khi không có `seniority_levels` do client truyền, service tự suy luận (heuristic bên dưới) rồi cũng áp dụng cùng cơ chế tách dòng nếu suy luận ra nhiều cấp bậc.

## Repository (`app/domains/market/repository.py`)

Filter helper dùng chung:
```python
def _apply_job_filters(self, query, *, location=None, career_id=None,
                        seniority_levels=None, salary_min=None, salary_max=None,
                        start=None, end=None):
    if location:
        query = query.filter(JobPosting.location == location)
    if career_id:
        query = query.filter(JobPosting.career_id == career_id)
    if seniority_levels:
        query = query.filter(JobPosting.seniority_level.in_(seniority_levels))
    if salary_min is not None:
        query = query.filter(JobPosting.salary_max.isnot(None), JobPosting.salary_max >= salary_min)
    if salary_max is not None:
        query = query.filter(JobPosting.salary_min.isnot(None), JobPosting.salary_min <= salary_max)
    if start is not None:
        query = query.filter(JobPosting.posted_at >= start)
    if end is not None:
        query = query.filter(JobPosting.posted_at < end)
    return query
```
"Mọi mức lương" = không truyền `salary_min`/`salary_max` → không lọc.

Method mới:
- `get_job_skill_sets() -> dict[int, set[int]]` — job_id -> skill_id set (từ `JobSkill`), dùng cho heuristic gán `job_id` lúc ingest.
- `get_career_general_skill_sets() -> dict[int, set[int]]` — career_id -> skill_id set (từ `CareerSkill`), dùng cho fallback case beginner khi không khớp `Job` nào.
- `get_jobs(trend=None, career_id=None) -> List[Job]`.
- `count_job_postings(*, start=None, end=None, **filters) -> int`
- `count_distinct_jobs_with_postings(**filters) -> int` — cho stat "Nhóm nghề".
- `count_distinct_skills_demanded(**filters) -> int`
- `get_last_posting_timestamp(**filters) -> Optional[datetime]`
- `get_weekly_posting_counts(*, weeks=8, **filters) -> list[tuple[date, int]]` (Postgres `func.date_trunc('week', posted_at)`).
- `get_yearly_average_weekly_count(**filters) -> float`
- `get_location_distribution(**filters) -> list[tuple[str, int]]`
- `get_job_demand_within_career(career_id, window_days=30, **filters) -> list[dict]` — per-`Job` 2-cửa-sổ demand/growth trong 1 Career, clone đúng cấu trúc `get_skill_demand_trend` hiện có nhưng group theo `Job` (qua `JobPosting.job_id`) — nguồn dữ liệu cho phần drill-down "đến từng nghề".

Sửa method hiện có:
- `get_skill_demand`, `get_skill_demand_trend`, `_skill_counts`: `location` thành `Optional[str] = None` (hỗ trợ "Toàn quốc"); dùng `JobPostingSkill` (đổi tên) thay vì `JobSkill` cũ.
- `update_career_trend` → `update_job_trend(job_id, trend)`; thêm rollup `Career.market_trend` sau khi tính hết Job.
- `get_all_career_ids` → `get_all_job_ids()`.
- `get_career_skill_ids(career_id)` → `get_job_skill_ids(job_id)` (đọc từ `JobSkill`).

## Service (`app/domains/market/service.py`)

Hằng số mới cạnh `TREND_GROWTH_THRESHOLD` (heuristic MVP, ghi rõ giả định):
```python
MIN_JOB_SKILL_OVERLAP = 1
MIN_CAREER_GENERAL_SKILL_OVERLAP = 1
CONFIDENCE_SAMPLE_THRESHOLDS = {"HIGH": 500, "MEDIUM": 100}
GROWTH_SPEED_THRESHOLDS = {"STRONG": 0.30, "MODERATE": TREND_GROWTH_THRESHOLD}  # tái dùng 0.15
SENIORITY_KEYWORDS = [...]  # keyword rẻ tiền, KHÔNG gọi chatbot (bulk ingest có thể hàng trăm dòng/lần)
```

Heuristic tất định (không gọi AI), **2 tầng** để xử lý case beginner:
```python
def _resolve_job_id(skill_ids, job_skill_map) -> Optional[int]:
    # job có nhiều skill trùng nhất với posting (>= MIN_JOB_SKILL_OVERLAP); None nếu không đủ tín hiệu
    # (case beginner: posting chỉ có skill chung chung như "Toán học" -> không trùng skill riêng
    # của Job nào -> trả None, rơi xuống tầng 2)

def _resolve_career_id_fallback(skill_ids, career_general_skill_map) -> Optional[int]:
    # CHỈ gọi khi _resolve_job_id trả None. Khớp theo CareerSkill (>= MIN_CAREER_GENERAL_SKILL_OVERLAP)
    # -> gán được career_id (biết đúng ngành) dù không xác định được Job cụ thể.

def _infer_seniority_levels(title) -> list[SeniorityLevel]:
    # match từ khoá trong title, trả list (thường 1 phần tử; >1 nếu title chứa cả 2 dạng vd. "Junior/Mid"),
    # mặc định [MID] nếu không khớp từ khoá nào
```
Cả 3 tính 1 lần/batch (`get_job_skill_sets()`/`get_career_general_skill_sets()` gọi 1 lần mỗi cái), không N+1.

`ingest_jobs` — logic 2-tầng gán career/job + fan-out đa cấp bậc thành nhiều dòng:
```python
def ingest_jobs(self, jobs: List[JobPostingCreate]):
    job_skill_map = self.repo.get_job_skill_sets()
    career_general_skill_map = self.repo.get_career_general_skill_sets()
    rows = []
    for j in jobs:
        data = j.model_dump()
        levels = data.pop("seniority_levels", None) or self._infer_seniority_levels(data["title"])
        if data.get("job_id") is None:
            data["job_id"] = self._resolve_job_id(data["skill_ids"], job_skill_map)
        if data.get("career_id") is None:
            if data["job_id"] is not None:
                data["career_id"] = job_id_to_career_id[data["job_id"]]  # tra từ Job đã khớp
            else:
                # Case beginner: không khớp Job nào -> thử khớp skill chung chung của ngành
                data["career_id"] = self._resolve_career_id_fallback(data["skill_ids"], career_general_skill_map)
        if data.get("posted_at") is None:
            data["posted_at"] = datetime.utcnow()
        for level in levels:  # >=1 phần tử luôn — 1 dòng cho mỗi cấp bậc trong tin gốc
            rows.append({**data, "seniority_level": level})
    return self.repo.bulk_create_jobs(rows)
```
Giá trị `job_id`/`career_id`/`seniority_levels` client truyền tường minh luôn được ưu tiên (giữ đúng precedent override của `posted_at` hiện có). Nếu cả 2 tầng đều không khớp, `job_id`/`career_id` để `None` — posting vẫn được lưu (không chặn ingest), chỉ không xuất hiện khi lọc theo ngành/nghề.

`update_market_trends(window_days=30)` — sửa để lặp theo `Job` (không phải `Career`), sau đó rollup lên `Career`:
```python
for job_id in self.repo.get_all_job_ids():
    skill_ids = self.repo.get_job_skill_ids(job_id)
    ... (giữ nguyên công thức RISING/STABLE/DECLINING hiện có)
    self.repo.update_job_trend(job_id, trend)
# rollup Career.market_trend từ union skill-set của các Job con (cùng công thức, join thêm 1 cấp)
```

Method tổng hợp mới cho dashboard:
```python
def get_market_overview(self, *, days=30, location=None, career_id=None,
                         seniority_levels=None, salary_min=None, salary_max=None) -> dict:
    # total_job_postings + mom_growth_rate (current/previous window)
    # job_group_count = count_distinct_jobs_with_postings   <- "Nhóm nghề" = số Job, không phải Career
    # skill_count = count_distinct_skills_demanded
    # last_updated_days_ago = MAX(posted_at) trong tập lọc (không có cột ingest riêng — giả định, ghi rõ)
    # confidence = bucket theo CONFIDENCE_SAMPLE_THRESHOLDS (giả định)
    # growth_speed = bucket theo GROWTH_SPEED_THRESHOLDS, None -> STABLE
    # chart = weekly_counts (8 tuần) + yearly_average_weekly_count
    # location_distribution = top 3 + "Khu vực khác", kèm %
```
Wrapper hẹp cho drill-down:
```python
def get_job_demand(self, career_id: int, window_days: int = 30, **filters) -> list[dict]:
    return self.repo.get_job_demand_within_career(career_id, window_days, **filters)
```

`seed_demo_data` — tái cấu trúc dữ liệu mẫu:
- Thêm 1 `Career` mẫu duy nhất: `{"title": "Công nghệ thông tin"}`.
- 5 "career" mẫu hiện có (Backend Developer, Frontend Developer, Data Scientist, DevOps Engineer, Business Analyst) → chuyển thành 5 **`Job`** mẫu, `career_id` đều trỏ về "Công nghệ thông tin".
- Thêm 3 skill chung chung mới vào `SEED_SKILLS` (category `"General"`): "Toán học", "Giải quyết vấn đề", "Tư duy logic" — link vào `CareerSkill` của "Công nghệ thông tin" (KHÔNG link vào Job nào).
- 38 job posting mẫu: backfill `job_id`/`career_id` tự động qua `_resolve_job_id`/(nếu None thì `_resolve_career_id_fallback`) — không hard-code.
- Thêm 2 posting mẫu mới kiểu **beginner**: chỉ gắn 1-2 skill chung chung ở trên (vd. "Giải quyết vấn đề", "Tư duy logic"), không gắn skill kỹ thuật cụ thể nào — minh hoạ đúng case: `job_id` ra `None` nhưng `career_id` vẫn được gán đúng "Công nghệ thông tin" qua tầng fallback.
- `seniority_level` **curate tay theo từng posting** (đơn trị) để demo có trải phổ đủ 5 mức; thêm 2-3 posting mẫu khác minh hoạ multi-level-source bằng cách khai `"seniority_levels": ["JUNIOR", "MID"]` ở input mẫu (service tự tách thành 2 dòng DB khi seed).
- Thêm `requirements`/`benefits` mẫu cho vài posting tiêu biểu (không bắt buộc mọi dòng) để minh hoạ field mới.

## Router (`app/domains/market/router.py`)

- `get_skill_demand`, `get_skill_demand_trend`: `location: Optional[str] = None`.
- `list_careers`: giữ nguyên (đã đúng cấp "ngành" cho industry dropdown).
- Thêm `GET /market/jobs?career_id=&trend=`.
- **1 endpoint tổng hợp** `GET /market/overview` — 4 stat card + chart tuần + phân bố khu vực trong 1 response (giống pattern `TaskProgressRead`/`get_task_progress` ở domain `task`).
- **1 endpoint hẹp** `GET /market/careers/{career_id}/jobs` — per-Job demand/growth trong 1 ngành (drill-down "đến từng nghề").

```python
@router.get("/overview", response_model=MarketOverviewRead)
def get_market_overview(days: int = 30, location: Optional[str] = None, career_id: Optional[int] = None,
                         seniority: Optional[List[SeniorityLevel]] = Query(None),
                         salary_min: Optional[int] = None, salary_max: Optional[int] = None,
                         db: Session = Depends(get_db)): ...

@router.get("/careers/{career_id}/jobs", response_model=List[JobDemandTrend])
def get_job_demand(career_id: int, window_days: int = 30, location=None, seniority=Query(None),
                    salary_min=None, salary_max=None, db: Session = Depends(get_db)): ...
```

## Schemas (`app/domains/market/schemas.py`)

Thêm `SeniorityLevel` (str, Enum — mirror schema, giống `MarketTrend`), `ConfidenceLevel` (HIGH/MEDIUM/LOW), `GrowthSpeed` (STRONG/MODERATE/STABLE/DECLINING). Thêm `JobBase/JobCreate/JobRead` (title, description, career_id, market_trend) — mirror `CareerBase/CareerCreate/CareerRead`. Mở rộng:
- `JobPostingCreate`: + `job_id: Optional[int] = None`, `seniority_levels: List[SeniorityLevel] = Field(default_factory=list, description="Nếu >1 phần tử, service tách thành nhiều JobPosting riêng, mỗi dòng 1 cấp bậc")`, `requirements: Optional[str] = None`, `benefits: Optional[str] = None`.
- `JobPostingRead`: + `job_id`, `seniority_level: Optional[SeniorityLevel]` (đơn trị — vì đây là 1 dòng DB thật), `requirements`, `benefits`.
Thêm `MarketOverviewStats`, `WeeklyPostingCount`, `MarketOverviewChart`, `LocationShare`, `MarketOverviewRead`, `JobDemandTrend` (title, demand_recent, demand_previous, growth_rate — mirror `SkillDemandTrend`).

## Lưu ý triển khai DB (Neon Postgres, không có Alembic)

Không tự chạy — cần thao tác thủ công trên Neon DB thật trước khi deploy, theo đúng thứ tự (vì bảng `job_skills`/`career_skills` cũ đổi tên/ý nghĩa):
1. Đổi tên bảng `job_skills` hiện có (JobPosting↔Skill) → `job_posting_skills`, đổi tên cột `job_id` → `job_posting_id`.
2. Tạo bảng `jobs`, và bảng `job_skills` MỚI (Job↔Skill, dùng để tính trend).
3. Migrate dữ liệu từ bảng `career_skills` cũ (Career↔Skill, dùng để tính trend) sang `jobs`/`job_skills` mới — mỗi `Career` cũ trở thành 1 `Job` mới. Sau đó `DROP` bảng `career_skills` cũ.
4. Tạo 1 `Career` mới đại diện ngành (vd. "Công nghệ thông tin") làm cha cho các `Job` vừa migrate.
5. Tạo bảng `career_skills` MỚI (Career↔Skill, skill chung chung/fallback — tên trùng bảng cũ ở bước 3 nhưng ý nghĩa khác, tạo sau khi bảng cũ đã bị xoá).
6. Thêm cột `job_id`, `career_id`, `seniority_level`, `requirements`, `benefits` vào `job_postings` (cần `CREATE TYPE senioritylevel` trước khi thêm cột enum).

Với môi trường demo/dev hiện tại, cách nhanh nhất là seed lại từ đầu qua `ENABLE_SEED_ENDPOINT` thay vì migrate dữ liệu cũ thủ công.

## Ngoài phạm vi

Phần nội dung bị cắt phía dưới màn hình (chữ "Nhóm ng..." lấp ló) — `GET /market/careers/{career_id}/jobs` là suy đoán hợp lý nhất cho phần đó, cần xác nhận lại khi thấy đủ UI.

## Files chính sẽ sửa
- `app/domains/market/models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `seed_data.py`

## Verification
1. `uv run --project .. pytest` — toàn bộ test cũ phải pass.
2. Boot server thật, gọi `POST /market/seed-demo-data`, sau đó:
   - `GET /market/careers/` → 1 career "Công nghệ thông tin".
   - `GET /market/jobs/` → 5 job (Backend Developer, Frontend Developer, Data Scientist, DevOps Engineer, Business Analyst), mỗi job có `market_trend` đúng như logic cũ (RISING/STABLE/DECLINING).
   - `GET /market/overview` (không filter) → `stats.total_job_postings` đúng tổng, `stats.job_group_count=5`, `stats.skill_count` >= 10 (10 skill kỹ thuật + 3 skill chung chung).
   - `GET /market/overview?career_id=<id CNTT>` → ra đủ toàn bộ (toàn bộ seed là IT).
   - `GET /market/overview?location=Ha Noi` → thu hẹp đúng.
   - `GET /market/overview?seniority=JUNIOR&seniority=INTERN` → gộp đúng 2 cấp bậc (tự "collect" ở tầng query).
   - `GET /market/careers/{id}/jobs` → breakdown theo 5 job, có demand_recent/previous/growth_rate.
   - Ingest 1 job posting mới qua `POST /market/jobs/bulk` với `seniority_levels: ["JUNIOR", "MID"]` → xác nhận tạo ra **2 dòng `JobPosting`** riêng (mỗi dòng 1 `seniority_level`), không phải 1 dòng đa trị.
   - Ingest 1 posting "beginner" chỉ có skill chung chung (vd. "Tư duy logic") → đọc lại posting: `job_id = null` nhưng `career_id` = đúng id "Công nghệ thông tin" (không phải cả 2 đều null) — xác nhận tầng fallback hoạt động.
   - `GET /market/analytics/skill-demand` (bỏ `location`) → không lỗi 422, trả toàn quốc.
3. `GET /openapi.json` thấy các route mới (`/market/overview`, `/market/jobs`, `/market/careers/{id}/jobs`) xuất hiện đúng.
