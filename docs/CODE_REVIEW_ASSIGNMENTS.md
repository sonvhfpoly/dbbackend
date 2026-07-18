# Code Review Assignments — 3 Dev, Toàn Bộ Codebase

Phân công review code hiện tại (8 domain), chia theo cụm domain có liên kết chặt (mỗi dev đủ context, không phải nhảy qua lại đọc code domain khác), cân theo khối lượng dòng code. Xem [ARCHITECTURE.md](ARCHITECTURE.md) cho bản đồ domain đầy đủ.

## Đọc chung trước khi review (cả 3 dev)

- [ARCHITECTURE.md](ARCHITECTURE.md) — kiến trúc, wiring rule, quyết định **không có Auth/RBAC** (đừng report thiếu auth như một bug — đó là quyết định có chủ đích, xem §3)
- [requirements.md](requirements.md) — spec gốc, dùng để đối chiếu business rule có implement đúng không
- [TESTING.md](TESTING.md) — cách chạy test/server để tự verify finding trước khi report

---

## Dev A — Market Intelligence & AI Chat Infra (~2.170 dòng)

| | |
|---|---|
| **Domain** | `market` (1380 dòng), `guidance` (472 dòng), `chatbot` (319 dòng) |
| **Test** | `test_market_service.py`, `test_anti_bias.py` |
| **Doc riêng** | [MARKET_DATA_MODEL.md](MARKET_DATA_MODEL.md) |

### Trọng tâm review
- Heuristic gán `job_id`/`career_id`/`seniority_level` lúc ingest (`_resolve_job_id`, `_resolve_career_id_fallback`, `_infer_seniority_levels`) — tất định, không AI, dễ sai edge case (posting không skill nào, trùng skill nhiều Job).
- `AntiBiasEngine` (Strategy Pattern) — đúng behavior `DiversityValidator`/`RegionExpansionValidator` theo yêu cầu đạo đức ở requirements §40.
- **`app/domains/chatbot/providers.py` vừa sửa** (thêm `json_mode` cho FPT Cloud + Vertex AI) — code mới nhất, risk cao nhất trong cụm này, nên soi kỹ.
- Enum dedup convention (`schemas.py` import từ `models.py`, không định nghĩa lại) — check `guidance`/`market` đã áp dụng đúng chưa.

---

## Dev B — Task Lifecycle (~2.100 dòng, phức tạp nhất)

| | |
|---|---|
| **Domain** | `task` (1462 dòng), `task_builder` (641 dòng) |
| **Test** | `test_task_service.py`, `test_task_review.py`, `test_task_submission_extras.py`, `test_task_builder_service.py` |
| **Doc riêng** | Phần Task trong [DATA_MODEL.md](DATA_MODEL.md) |

### Trọng tâm review
- State machine `SubmissionStatus` + `TaskReviewStatus` — mọi transition có validate đúng ở service layer không (đặc biệt gate R2/R3 chặn `APPROVED`, `join_task` yêu cầu `review_status=APPROVED`).
- `complexity_level` (T1-T3) — field `difficulty` cũ đã gỡ hoàn toàn, check không còn sót reference nào.
- `skip_ai_planning` flag + luồng `task_builder.generate_task` gọi `TaskService.create_task()` — xác nhận không còn code path trùng lặp.
- **Bug vừa fix**: `TaskBuilderService._complete_and_parse` (retry + fallback khi AI trả JSON sai định dạng) — phần rủi ro nhất, nên tự tay giả lập lại bug (AI trả prose) để xác nhận không còn regress.
- Giới hạn file upload (50MB/file, 10 file/submission), `elapsed_seconds`/`student_reflection`.

---

## Dev C — Student Profile, Evidence, ePortfolio & Infra (~1.770 dòng)

| | |
|---|---|
| **Domain** | `student` (959 dòng), `evidence` (319 dòng), `eportfolio` (280 dòng), `core` (107 dòng), `alembic` (101 dòng) |
| **Test** | `test_evidence_service.py` |
| **Doc riêng** | Phần Evidence/ePortfolio trong [DATA_MODEL.md](DATA_MODEL.md) |

### Trọng tâm review
- `EvidenceClaim` state machine (`AI_DRAFT→...→VERIFIED`) — xác nhận **chỉ** `VERIFIED` mới gọi `StudentProfileService.create_student_skill_event` (điểm human-in-the-loop quan trọng nhất hệ thống, xem requirements §29).
- `eportfolio` — không có cache, tổng hợp real-time từ 4 domain khác; check `business-view` thực sự `403` khi chưa consent, và không lộ field nào ngoài whitelist.
- `core/config.py`/`main.py` — `AUTO_CREATE_SCHEMA` + Alembic setup, xác nhận `alembic upgrade head` không bị conflict với `create_all()` fallback.
- **Gap cần lưu ý**: `student` domain hiện **không có file test riêng** (`test_student_service.py` không tồn tại) — nên tự đánh giá xem có đáng bổ sung không, đặc biệt phần `create_student_skill_event` (logic tính `level_delta`/`confidence` merge).

---

## Format báo cáo đề xuất

Mỗi dev report theo: **file:dòng → mô tả bug/risk → mức độ (blocker/nên sửa/nitpick) → đề xuất fix**.

Ưu tiên tổng hợp lại thành 1 buổi sync để bắt các vấn đề **xuyên domain** (vd. Dev B và Dev C cùng xem lại điểm nối `task_id`/`skill_id` giữa `task` và `evidence`).
