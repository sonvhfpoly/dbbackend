# Plan: Job Detail + Profile-Match API cho trang "Phân tích vận hành" (student-facing)

## Context

Trang chi tiết Job phía student ("Phân tích vận hành", dưới mục "Cơ hội thị trường") cần 2 việc phía backend: (1) xem chi tiết 1 `Job` (nghề cụ thể, vd. "DevOps") kèm số liệu thị trường tổng hợp, và (2) panel "Liên hệ với hồ sơ của tôi" — % phù hợp giữa skill của student và skill nghề này yêu cầu, chia 2 nhóm Đã có / Cần bổ sung.

Nền tảng đã có sẵn từ 2 plan trước: domain `market` đã có `Job`↔`JobSkill`↔`Skill` (curated skillset định nghĩa 1 Job, dùng tính `market_trend`), domain `student` đã có `StudentSkill (student_id, skill_id)` + seed data 3 student mẫu. Plan này xây phần còn thiếu: **Job detail endpoint** (market domain) và **service/schema/router mới cho domain `student`** (domain này hiện chỉ có `models.py`/`repository.py`/`seed_data.py`, tag "Student Profile" đã khai báo sẵn trong `main.py` nhưng chưa có router nào dùng).

**Đã chốt qua AskUserQuestion (không hỏi lại):**
- StudentSkill không có proficiency/level → panel match chỉ có **2 nhóm thật** (Đã có / Cần bổ sung), không có nhóm "Đang phát triển" giả — match_percent = |giao StudentSkill ∩ JobSkill| / |JobSkill|.
- "Hoạt động tiêu biểu" **không nằm trong phạm vi plan này** (chưa có nguồn dữ liệu hợp lý, để lại vòng sau).

**Mở rộng (vòng sau, cùng phiên) — bổ sung các phần còn lại của trang 5-tab đầy đủ** (badge, tab Nhiệm vụ, Lưu cấu hình): xem mục 3 và 4 bên dưới. Quyết định mới:
- Tab **"Nhiệm vụ"** suy ra qua skill chung, không thêm FK trực tiếp `Task.job_id` — vì `task.Task` hiện không có bất kỳ liên kết skill nào (`TaskEvaluationCriterion` là free-text), cần thêm 1 bảng liên kết `Task`↔`Skill` mới nhẹ (cùng pattern `JobSkill`), rồi so khớp với `Job.skills`.
- Badge "Nhu cầu cao" / "Dữ liệu & Vận hành" và số "Nhu cầu tuyển dụng 12 tháng tới: +15%": tái dùng dữ liệu đã có (`market_trend`, `career.title`) + 1 field mới `demand_growth_rate_estimate` (xấp xỉ, không phải dự báo 12-tháng thật, ghi rõ trong description).
- "Lưu cấu hình" / "Chia sẻ": bookmark mới, gắn vào `student` router (đang được tạo mới ở mục 2).

## 1. Job detail — mở rộng domain `market`

**`app/domains/market/repository.py`**: thêm
- `get_job(job_id: int) -> Optional[Job]` (single-get còn thiếu — hiện chỉ có `get_jobs()` list).
- `get_average_salary_range(job_id: int) -> Tuple[Optional[int], Optional[int]]` — `func.avg(salary_min/max)` trên các `JobPosting` của job đó, bỏ qua NULL.
- `get_seniority_distribution(job_id: int) -> List[Tuple[str, int]]` — group by `seniority_level`.
- Thêm `job_id=None` vào `_apply_job_filters` (song song với `career_id` đã có) → `count_job_postings(job_id=...)` và `get_location_distribution(job_id=...)` dùng lại được ngay, không cần method mới cho 2 số liệu này.

**`app/domains/market/service.py`**: thêm `get_job_detail(job_id) -> dict`:
```python
def get_job_detail(self, job_id: int) -> dict:
    job = self.repo.get_job(job_id)
    if job is None:
        raise EntityNotFoundException("Job", job_id)
    avg_min, avg_max = self.repo.get_average_salary_range(job_id)
    return {
        "id": job.id, "title": job.title, "description": job.description,
        "career_id": job.career_id, "career_title": job.career.title,
        "market_trend": job.market_trend,
        "skills": job.skills,  # relationship đã có sẵn trên Job model — không cần query riêng
        "stats": {
            "posting_count": self.repo.count_job_postings(job_id=job_id),
            "avg_salary_min": avg_min, "avg_salary_max": avg_max,
            "top_locations": self._to_location_shares(self.repo.get_location_distribution(job_id=job_id)),
            "seniority_distribution": [
                {"level": level, "count": count}
                for level, count in self.repo.get_seniority_distribution(job_id)
            ],
        },
    }
```
Tái dùng `_to_location_shares` đã có (top-3 + "Khu vuc khac").

**`app/domains/market/schemas.py`**: thêm `SeniorityDistribution(level, count)`, `JobStats(posting_count, avg_salary_min, avg_salary_max, top_locations: List[LocationShare], seniority_distribution: List[SeniorityDistribution])`, `JobDetailRead(JobRead)` mở rộng `career_title: str`, `skills: List[SkillRead]`, `stats: JobStats`.

**`app/domains/market/router.py`**: thêm `GET /market/jobs/{job_id}` → `response_model=JobDetailRead`.

## 2. Profile match — domain `student` (mới: service + schemas + router)

**`app/domains/student/repository.py`**: thêm `get_student_skill_ids(student_id) -> List[int]` (query `StudentSkill.skill_id` filter theo `student_id`).

**`app/domains/market/repository.py`**: thêm `get_skills_by_ids(skill_ids) -> List[Skill]` (query `IN`, trả `[]` nếu list rỗng) — dùng để lấy chi tiết (name/category) cho have/missing skills.

**`app/domains/student/schemas.py`** (mới):
```python
from domains.market.schemas import SkillRead  # tái dùng, không định nghĩa lại

class StudentRead(BaseModel):
    id: int; full_name: str; email: str; current_location: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class JobMatchRead(BaseModel):
    job_id: int
    job_title: str
    match_percent: Optional[float] = Field(description="None khi Job chưa có skill nào trong JobSkill (chưa đủ dữ liệu để tính)")
    have_skills: List[SkillRead]
    missing_skills: List[SkillRead]
    is_saved: bool = False
```

**`app/domains/student/service.py`** (mới):
```python
class StudentService:
    def __init__(self, db: Session):
        self.repo = StudentRepository(db)
        self.market_repo = MarketRepository(db)

    def get_student(self, student_id: int) -> Student:
        student = self.repo.get_student(student_id)
        if student is None:
            raise EntityNotFoundException("Student", student_id)
        return student

    def get_job_match(self, student_id: int, job_id: int) -> dict:
        student = self.get_student(student_id)
        job = self.market_repo.get_job(job_id)
        if job is None:
            raise EntityNotFoundException("Job", job_id)

        job_skill_ids = set(self.market_repo.get_job_skill_ids(job_id))
        student_skill_ids = set(self.repo.get_student_skill_ids(student_id))
        have_ids = job_skill_ids & student_skill_ids
        missing_ids = job_skill_ids - student_skill_ids
        match_percent = round(len(have_ids) / len(job_skill_ids) * 100, 1) if job_skill_ids else None

        return {
            "job_id": job.id, "job_title": job.title,
            "match_percent": match_percent,
            "have_skills": self.market_repo.get_skills_by_ids(have_ids),
            "missing_skills": self.market_repo.get_skills_by_ids(missing_ids),
            "is_saved": self.market_repo.is_job_saved(student_id, job_id),
        }
```
Tái dùng `MarketRepository.get_job_skill_ids` đã có sẵn (dùng cho `update_market_trends`) — không viết lại.

**`app/domains/student/router.py`** (mới):
```python
router = APIRouter(prefix="/students", tags=["Student Profile"])  # tag đã khai báo sẵn trong main.py, chưa domain nào dùng

@router.get("/{student_id}", response_model=StudentRead, summary="Get a student's profile")
def get_student(student_id: int, db: Session = Depends(get_db)):
    return StudentService(db).get_student(student_id)

@router.get(
    "/{student_id}/jobs/{job_id}/match",
    response_model=JobMatchRead,
    summary="Compare a student's skills against a Job's required skillset",
    description="match_percent = |StudentSkill ∩ JobSkill| / |JobSkill|. "
                "'Đang phát triển' (in-progress) is intentionally not modeled — StudentSkill "
                "has no proficiency/level column, and no other data source ties an in-progress "
                "signal to a specific skill.",
)
def get_job_match(student_id: int, job_id: int, db: Session = Depends(get_db)):
    return StudentService(db).get_job_match(student_id, job_id)

@router.post("/{student_id}/saved-jobs/{job_id}", summary="Bookmark a job ('Lưu cấu hình')")
def save_job(student_id: int, job_id: int, db: Session = Depends(get_db)):
    return StudentService(db).save_job(student_id, job_id)

@router.delete("/{student_id}/saved-jobs/{job_id}", summary="Remove a bookmark")
def unsave_job(student_id: int, job_id: int, db: Session = Depends(get_db)):
    return StudentService(db).unsave_job(student_id, job_id)

@router.get("/{student_id}/saved-jobs", summary="List a student's bookmarked jobs")
def list_saved_jobs(student_id: int, db: Session = Depends(get_db)):
    return StudentService(db).list_saved_jobs(student_id)
```

**`app/main.py`**: import `from domains.student.router import router as student_router`, thêm `app.include_router(student_router)`.

## 3. Tab "Nhiệm vụ" — liên kết Task ↔ Job qua skill chung

`task.Task` hiện không có cột/bảng liên kết `Skill` nào — cần thêm trước khi so khớp được.

**`app/domains/task/models.py`**: thêm bảng liên kết mới (skill thuộc `market.Skill`, task domain trỏ tới bằng ForeignKey thô như các domain khác đã làm với bảng dùng chung, không import model chéo):
```python
class TaskSkill(Base):
    __tablename__ = "task_skills"
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
```
`Task.skills = relationship("Skill", secondary="task_skills")` — quan hệ này chỉ dùng để filter, không cần load full `Skill` object từ phía task domain thường xuyên.

**`app/domains/task/repository.py`**: thêm `get_tasks_by_skill_ids(skill_ids: List[int]) -> List[Task]` — join `TaskSkill`, lọc `Task.parent_task_id IS NULL` (chỉ task gốc, không lộ sub-task rời trong danh sách gợi ý), match ANY skill (giống cách `get_job_count_for_skills` bên market match ANY), distinct theo `Task.id`.

**`app/domains/market/service.py`**: `MarketService.__init__` cần lưu thêm `self.db = db` (hiện chỉ lưu `self.repo`) để tạo `TaskRepository(self.db)` khi cần — theo đúng tiền lệ `guidance/service.py` đã import thẳng `MarketRepository` (cross-domain repository import là pattern đã có, không phải vi phạm mới):
```python
from domains.task.repository import TaskRepository

def get_job_missions(self, job_id: int):
    job = self.repo.get_job(job_id)
    if job is None:
        raise EntityNotFoundException("Job", job_id)
    skill_ids = [s.id for s in job.skills]
    if not skill_ids:
        return []
    return TaskRepository(self.db).get_tasks_by_skill_ids(skill_ids)
```

**`app/domains/market/router.py`**: `GET /market/jobs/{job_id}/missions` → `response_model=List[TaskRead]` (import từ `domains.task.schemas`, tái dùng — không định nghĩa lại DTO task).

**Giả định cần lưu ý**: tab này chỉ có dữ liệu khi task thật sự được gắn `TaskSkill` — cần cập nhật `task/seed_data.py` gắn skill mẫu (từ `market.Skill`) cho >= 1 task hiện có, nếu không tab "Nhiệm vụ" sẽ luôn trả về rỗng dù đúng logic.

## 4. Badge + số tăng trưởng nhu cầu + Lưu cấu hình/Chia sẻ

**`app/domains/market/repository.py`**: thêm `get_job_growth_rate(job_id, window_days=30) -> Optional[float]` — 2-cửa-sổ giống `update_market_trends` nhưng trả raw rate (không bucket hoá thành RISING/STABLE/DECLINING), dùng `job_id` filter vừa thêm ở mục 1 để đếm postings của riêng job này (không lẫn qua job khác dù trùng skill — khác với `Job.market_trend` vốn tính qua skill-overlap toàn hệ thống).

**`app/domains/market/service.py`**: thêm `growth_rate_estimate` vào `get_job_detail()`'s `stats` dict, gọi `get_job_growth_rate`. Ghi rõ trong docstring/schema description: đây là xấp xỉ từ tăng trưởng 30-ngày gần nhất, KHÔNG phải mô hình dự báo 12 tháng thật (không có model dự báo nào trong hệ thống).

**`app/domains/market/schemas.py`**: `JobStats` thêm field `growth_rate_estimate: Optional[float] = Field(description="Xấp xỉ từ tăng trưởng 2 cửa sổ 30 ngày gần nhất — KHÔNG phải dự báo 12 tháng thật")`.

**Bookmark ("Lưu cấu hình")** — entity mới, nhẹ, cùng phong cách loose-reference `student_id` đã dùng ở `TaskSubmission`:
```python
# app/domains/market/models.py
class SavedJob(Base):
    __tablename__ = "saved_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, index=True)  # loose ref, không FK — Student ở service khác
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```
Gắn vào **student router** (mục 2) vì đây là hành động của student, không phải thuộc tính của Job:
```
POST   /students/{student_id}/saved-jobs/{job_id}    # Lưu cấu hình — idempotent, gọi lại không tạo trùng
DELETE /students/{student_id}/saved-jobs/{job_id}    # Bỏ lưu
GET    /students/{student_id}/saved-jobs             # (tương lai: trang "Đã lưu" riêng)
```
Thêm `is_saved: bool` vào `JobMatchRead` (mục 2) để trang chi tiết biết trạng thái nút Lưu ngay trong 1 lần gọi `/match`, không cần round-trip riêng.

"Chia sẻ" không cần backend — chỉ là copy link phía frontend.

## Files chính sẽ sửa/tạo
- Sửa: `app/domains/market/repository.py` (`get_job`, `get_average_salary_range`, `get_seniority_distribution`, `get_skills_by_ids`, `get_job_growth_rate`, `job_id` filter trong `_apply_job_filters`, `save_job`/`unsave_job`/`is_job_saved`/`list_saved_jobs`)
- Sửa: `app/domains/market/models.py` (`SavedJob`)
- Sửa: `app/domains/market/service.py` (`get_job_detail` + `growth_rate_estimate`, `get_job_missions`, lưu `self.db`)
- Sửa: `app/domains/market/schemas.py` (`SeniorityDistribution`, `JobStats` + `growth_rate_estimate`, `JobDetailRead`)
- Sửa: `app/domains/market/router.py` (`GET /market/jobs/{job_id}`, `GET /market/jobs/{job_id}/missions`)
- Sửa: `app/domains/task/models.py` (`TaskSkill`)
- Sửa: `app/domains/task/repository.py` (`get_tasks_by_skill_ids`)
- Sửa: `app/domains/task/seed_data.py` (gắn skill mẫu cho >=1 task, để tab Nhiệm vụ không rỗng khi demo)
- Sửa: `app/domains/student/repository.py` (`get_student_skill_ids`)
- Mới: `app/domains/student/schemas.py`, `app/domains/student/service.py`, `app/domains/student/router.py`
- Sửa: `app/main.py` (đăng ký `student_router`; `TaskSkill`/`SavedJob` được tạo bảng tự động qua `create_all` một khi models được import)
- Mới: `app/tests/unit/test_student_service.py` (theo pattern `object.__new__` + `FakeRepo` đã dùng ở `test_market_service.py`/`test_task_service.py`)

## Test coverage cần thêm
- `MarketService.get_job_detail`: job không tồn tại → `EntityNotFoundException`; happy path trả đúng shape (stats từ FakeRepo), bao gồm `growth_rate_estimate`.
- `MarketService.get_job_missions`: job không có skill nào → `[]` không lỗi; job có skill → trả đúng task giao skill (FakeRepo cho `TaskRepository`).
- `StudentService.get_job_match`: overlap một phần (%đúng), 100% match, 0% match, Job không có skill nào (`match_percent is None`, `missing_skills == []`), student không tồn tại → 404, job không tồn tại → 404, `is_saved` đúng true/false.
- Bookmark: lưu 2 lần không tạo trùng (idempotent), bỏ lưu rồi lưu lại hoạt động đúng.

## Verification
1. `uv run --project .. pytest -q` — toàn bộ test cũ (52) + test mới phải pass.
2. Boot server thật, gọi `GET /market/jobs/{id}` với 1 job đã seed (từ `SEED_JOBS`) → kiểm tra `stats.posting_count`, `top_locations`, `seniority_distribution`, `growth_rate_estimate` khớp dữ liệu seed.
3. Gọi `GET /students/{id}/jobs/{job_id}/match` với 1 student đã seed (từ `SEED_STUDENTS`) có skill giao với job đó → `match_percent` khớp tính tay `(|have|/|job_skill_ids|)*100`, `have_skills`/`missing_skills` đúng danh sách, `is_saved: false` ban đầu.
4. Gọi lại với 1 job không có `JobSkill` nào (nếu có trong seed) → xác nhận `match_percent: null`.
5. Gắn `TaskSkill` mẫu cho 1 task trùng skill với 1 job đã seed → `GET /market/jobs/{job_id}/missions` thấy đúng task đó; job khác không giao skill → `[]`.
6. `POST /students/{id}/saved-jobs/{job_id}` 2 lần liên tiếp → không tạo 2 dòng `SavedJob`; `GET .../match` sau đó thấy `is_saved: true`; `DELETE` xong gọi lại `is_saved: false`.
