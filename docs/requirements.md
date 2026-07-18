# WORKLAB — Product Requirements Specification

### Input tổng hợp cho Backend, AI và Frontend

> **Phiên bản:** MVP / Demo Path
> **Tác nhân chính:** Business — Mentor/Teacher — Student
> **Nguyên tắc vận hành:** Phần lớn task từ doanh nghiệp được đăng miễn phí. Không có Expert Reviewer trong MVP. Mentor/Giáo viên là người duyệt và xác nhận chính. AI chỉ đề xuất, con người ra quyết định cuối cùng.

---

# 1. Tổng quan sản phẩm

**WORKLAB** là nền tảng kết nối doanh nghiệp, giáo viên và sinh viên thông qua các nhiệm vụ nghề nghiệp thực tế hoặc mô phỏng.

Doanh nghiệp đưa ra một bài toán hoặc brief chưa có cấu trúc. AI giúp chuyển đổi brief thành một nhiệm vụ học tập rõ ràng. Giáo viên kiểm tra, duyệt và phân công nhiệm vụ. Sinh viên nhận task, thực hiện bằng công cụ bên ngoài WORKLAB, có thể sử dụng AI Mentor để hỗ trợ, sau đó tải file hoàn thành lên hệ thống.

AI phân tích đầu ra và tạo nhận xét sơ bộ. Giáo viên kiểm tra, xác nhận kết quả và bằng chứng năng lực. Evidence được cập nhật vào ePortfolio của sinh viên.

WORKLAB không phải:

* nền tảng freelance;
* công cụ outsourcing sinh viên;
* ATS tuyển dụng;
* LMS truyền thống;
* hệ thống career fit score;
* công cụ đánh giá con người bằng một điểm tổng.

---

# 2. Ba tác nhân chính

## 2.1. WORKLAB for Business

Doanh nghiệp có thể:

* tạo task bằng AI Chat;
* nhập brief chưa có cấu trúc;
* upload tài liệu đầu vào;
* nhận đề xuất task có cấu trúc;
* xem T-level và R-level;
* chọn biến thể task L1/L2;
* gửi task đến giáo viên;
* theo dõi trạng thái;
* nhận đầu ra đã được giáo viên duyệt;
* gửi feedback;
* xem ePortfolio sinh viên nếu sinh viên cho phép.

Phần lớn task trong MVP:

> **Free Learning Task**

Doanh nghiệp không phải trả phí để đăng task.

---

## 2.2. WORKLAB for Mentor

Mentor/Giáo viên có thể:

* xem dashboard thị trường lao động;
* xem nghề trending theo khu vực;
* xem kỹ năng đang có nhu cầu;
* quản lý danh sách sinh viên;
* xem task từ doanh nghiệp;
* duyệt hoặc từ chối task;
* chỉnh T-level/R-level trong phạm vi MVP;
* assign sinh viên;
* tạo nhóm;
* theo dõi trạng thái task;
* xem file sinh viên nộp;
* xem AI Evaluation;
* gửi feedback;
* yêu cầu sửa;
* xác nhận Evidence;
* cập nhật Skill Level;
* xem ePortfolio sinh viên;
* hỗ trợ lộ trình học tập.

Trong MVP không có Expert Reviewer.

---

## 2.3. WORKLAB for Student

Sinh viên có thể:

* xem Trang chủ;
* xem Cơ hội thị trường;
* xem Nhiệm vụ;
* xem ePortfolio;
* xem Lộ trình học tập;
* xem task urgent;
* nhận task;
* tải tài liệu đầu vào;
* làm task bằng công cụ bên ngoài;
* sử dụng AI Mentor;
* upload file hoàn thành;
* submit;
* nhận feedback;
* sửa và gửi lại;
* tích lũy Evidence;
* xem sự phát triển kỹ năng;
* xem gợi ý nghề nghiệp;
* xem task tiếp theo nên thử.

---

# 3. Core Product Flow

```text
BUSINESS
Tạo brief chưa có cấu trúc
        ↓
AI TASK BUILDER
Hỏi làm rõ
        ↓
AI STRUCTURING
Tạo task có cấu trúc
        ↓
BUSINESS
Chọn biến thể và gửi task
        ↓
MENTOR
Review
        ↓
Approve / Request Changes / Reject
        ↓
MENTOR
Assign Student / Create Team
        ↓
STUDENT
Accept Task
        ↓
accepted_at được ghi nhận
        ↓
STUDENT
Download Input
        ↓
Làm task bằng công cụ bên ngoài WORKLAB
        ↓
Optional: AI Mentor
        ↓
Upload Completed File
        ↓
Submit
        ↓
submitted_at được ghi nhận
        ↓
AI
Draft Evaluation + Draft Evidence
        ↓
MENTOR
Review + Feedback
        ↓
Approve / Request Revision
        ↓
MENTOR
Verify Evidence
        ↓
BUSINESS
Nhận output được phép chia sẻ
        ↓
STUDENT
ePortfolio + Skill Progression + Career Suggestions
```

---

# 4. Product Constraints

## 4.1. Task Complexity — T-level

| Level |      MVP | Mô tả                          |
| ----- | -------: | ------------------------------ |
| T1    |       Có | Micro-task, brief rõ           |
| T2    |       Có | Task có hướng dẫn/checkpoint   |
| T3    | Giới hạn | Mentor phải đủ khả năng review |
| T4    |    Không | Ngoài MVP                      |
| T5    |    Không | Ngoài MVP                      |

---

## 4.2. Task Risk — R-level

| Level |   MVP | Rule                           |
| ----- | ----: | ------------------------------ |
| R0    |    Có | Dữ liệu giả lập/công khai      |
| R1    |    Có | Dữ liệu ít rủi ro, đã làm sạch |
| R2    | Không | Không có chuyên gia trong MVP  |
| R3    | Không | Tự động không cho publish      |

Backend bắt buộc enforce:

```text
IF risk_level >= R2
THEN task cannot transition to APPROVED
```

---

## 4.3. Student Skill Level

MVP tập trung vào:

* L1;
* L2;
* một phần L3.

Không triển khai governance đầy đủ cho L4–L5.

Skill Level được lưu **theo từng skill**.

Đúng:

```json
{
  "skills": [
    {
      "skill_id": "legal_translation",
      "level": "L1"
    },
    {
      "skill_id": "document_formatting",
      "level": "L2"
    }
  ]
}
```

Không dùng:

```json
{
  "student_level": "L2"
}
```

---

# 5. Role & Permission Matrix

| Function            |   Business | Mentor | Student |
| ------------------- | ---------: | -----: | ------: |
| Tạo task            |          ✓ |      — |       — |
| Chat AI tạo task    |          ✓ |      — |       — |
| Upload task input   |          ✓ |      — |       — |
| Gửi task            |          ✓ |      — |       — |
| Approve task        |          — |      ✓ |       — |
| Reject task         |          — |      ✓ |       — |
| Assign student      |          — |      ✓ |       — |
| Create team         |          — |      ✓ |      ✓* |
| Accept task         |          — |      — |       ✓ |
| Download task input |          — |      ✓ |       ✓ |
| Chat AI Mentor      |          — |      — |       ✓ |
| Upload output       |          — |      — |       ✓ |
| Submit task         |          — |      — |       ✓ |
| Xem AI Evaluation   |   Giới hạn |      ✓ |       ✓ |
| Review submission   |          — |      ✓ |       — |
| Request revision    |          — |      ✓ |       — |
| Verify Evidence     |          — |      ✓ |       — |
| Feedback output     |          ✓ |      ✓ |       — |
| Xem ePortfolio      | Có consent |      ✓ |       ✓ |
| Share ePortfolio    |          — |      — |       ✓ |

`*` Student chỉ tạo team khi task cho phép.

---

# 6. Functional Requirements — Business

| ID     | Requirement         | Input                | Process                 | Output                 | Constraints                  | Team         |
| ------ | ------------------- | -------------------- | ----------------------- | ---------------------- | ---------------------------- | ------------ |
| BUS-01 | AI Task Chat        | Text                 | Save conversation + AI  | Chat response          | Không auto publish           | FE + BE + AI |
| BUS-02 | Upload document     | File/URL             | Validate + scan         | Document               | Private storage              | FE + BE      |
| BUS-03 | AI clarification    | Brief                | Detect missing fields   | Questions              | Ngắn, theo từng bước         | AI           |
| BUS-04 | AI task structuring | Brief + answer       | Extract task schema     | Task Draft             | AI-generated label           | AI + BE      |
| BUS-05 | Suggest T-level     | Task                 | Complexity analysis     | T1–T3                  | T4–T5 out                    | AI           |
| BUS-06 | Suggest R-level     | Task + file metadata | Risk analysis           | R0/R1                  | R2–R3 blocked                | AI           |
| BUS-07 | Create variants     | Structured task      | Generate L1/L2 variants | Task variants          | Không phải final Skill Level | AI           |
| BUS-08 | Preview task        | Task draft           | Render                  | Preview                | Editable                     |              |
| BUS-09 | Send task           | Selected variant     | Validate                | Pending approval       | Chưa visible với student     | BE           |
| BUS-10 | Track task          | Task ID              | Fetch state             | Timeline               | Read-only state              |              |
| BUS-11 | View result         | Approved submission  | Permission filter       | Files + review         | Không xem private log        |              |
| BUS-12 | Feedback            | Text                 | Save                    | EnterpriseReview       | Không thay Evidence          |              |
| BUS-13 | View ePortfolio     | Share permission     | Permission check        | Professional portfolio | Consent required             |              |

---

# 7. Task Creation Data

## 7.1. Business Input

| Field                 | Type     | Required |
| --------------------- | -------- | -------: |
| organization_id       | UUID     |        ✓ |
| created_by            | UUID     |        ✓ |
| original_brief        | text     |        ✓ |
| attachments           | array    |        — |
| desired_output        | text     |        — |
| target_student_level  | enum     |        — |
| deadline              | datetime |        — |
| team_preference       | enum     |        — |
| business_usage_intent | enum     |        ✓ |

`business_usage_intent`:

```text
LEARNING_ONLY
OPTIONAL_BUSINESS_USE
```

---

## 7.2. AI Structured Task Output

```json
{
  "title": "",
  "context": "",
  "problem_statement": "",
  "scope": [],
  "out_of_scope": [],
  "inputs": [],
  "deliverables": [],
  "acceptance_criteria": [],
  "skill_tags": [],
  "target_evidence_level": "L1",
  "task_complexity": "T1",
  "risk_level": "R0",
  "estimated_duration": {
    "value": 2,
    "unit": "DAY"
  },
  "team_mode": "INDIVIDUAL",
  "checkpoints": [],
  "ai_policy": {},
  "data_policy": {},
  "assumptions": [],
  "missing_information": []
}
```

Lưu ý:

`estimated_duration` là thời gian dự kiến từ khi nhận đến deadline, không phải số giờ làm việc thực tế.

---

# 8. Functional Requirements — Mentor

| ID     | Requirement        | Input             | Process          | Output             | Constraint         |
| ------ | ------------------ | ----------------- | ---------------- | ------------------ | ------------------ |
| MEN-01 | Dashboard          | Mentor ID         | Aggregate        | Dashboard          | Permission scoped  |
| MEN-02 | Market overview    | Region/time       | Aggregate        | Charts             | Source required    |
| MEN-03 | Trending jobs      | Region            | Rank signals     | Job groups         | Không “best job”   |
| MEN-04 | Skill demand       | Region/job        | Aggregate        | Skill signals      | Có limitation      |
| MEN-05 | Approval Queue     | Mentor scope      | Query task       | Pending list       | —                  |
| MEN-06 | Review Task        | Task ID           | Fetch brief + AI | Review UI          | Xem brief gốc      |
| MEN-07 | Approve            | Decision          | Validate         | APPROVED           | R0/R1              |
| MEN-08 | Request Changes    | Comment           | Transition       | NEED_MORE_INFO     | Audit              |
| MEN-09 | Reject Task        | Reason            | Transition       | REJECTED           | Audit              |
| MEN-10 | Assign Student     | Student + task    | Validate         | Assignment         | Human decision     |
| MEN-11 | Create Team        | Students          | Validate         | Team               | Team-mode only     |
| MEN-12 | Monitor Tasks      | Scope             | Aggregate states | Task list          | Không surveillance |
| MEN-13 | Review Submission  | Submission        | Fetch files      | Review             | —                  |
| MEN-14 | AI Evaluation      | Submission        | Fetch AI result  | Evaluation         | Draft only         |
| MEN-15 | Request Revision   | Feedback          | Update state     | REVISION_REQUESTED | —                  |
| MEN-16 | Approve Submission | Decision          | Update state     | APPROVED           | Audit              |
| MEN-17 | Verify Evidence    | Evidence draft    | Human decision   | VERIFIED           | Human final        |
| MEN-18 | Update Skill       | Verified evidence | Rubric logic     | Skill State        | Skill-specific     |
| MEN-19 | View ePortfolio    | Student ID        | Fetch            | Portfolio          | Scope based        |

---

# 9. Mentor Approval Input/Output

## Input

```json
{
  "task_id": "task_001",
  "reviewer_id": "mentor_001",
  "complexity_decision": "T1",
  "risk_decision": "R0",
  "learning_value": "APPROPRIATE",
  "target_evidence_level": "L1",
  "comment": "Phù hợp với sinh viên bắt đầu."
}
```

## Output

```json
{
  "task_review_id": "review_001",
  "task_id": "task_001",
  "decision": "APPROVED",
  "approved_complexity": "T1",
  "approved_risk": "R0",
  "approved_by": "mentor_001",
  "approved_at": "",
  "task_status": "APPROVED"
}
```

Constraints:

* Mentor phải thấy AI rationale.
* Mentor có thể override AI.
* Override bắt buộc có reason.
* Không approve R2/R3.
* Không có Expert Reviewer.

---

# 10. Functional Requirements — Student

| ID     | Requirement              | Input              | Process           | Output            | Constraints                  |
| ------ | ------------------------ | ------------------ | ----------------- | ----------------- | ---------------------------- |
| STU-01 | Home                     | Student ID         | Aggregate         | Dashboard         | Không overall score          |
| STU-02 | Urgent Tasks             | Student ID         | Deadline query    | Cards             | Urgent red                   |
| STU-03 | Market Opportunities     | Region             | Query             | Jobs              | Source/confidence            |
| STU-04 | Career Suggestions       | Skill/evidence     | Matching          | Careers           | Không fit %                  |
| STU-05 | Available Tasks          | Student ID         | Eligibility       | Approved Tasks    | —                            |
| STU-06 | Accept Task              | Task ID            | Create assignment | Active Task       | Ghi accepted_at              |
| STU-07 | Create/Join Team         | Task + members     | Validate          | Team              | Nếu được phép                |
| STU-08 | View Time Since Accepted | accepted_at        | Calculate         | Elapsed time      | Không dùng đánh giá năng lực |
| STU-09 | Download Input           | File ID            | Permission check  | Download          | Signed URL                   |
| STU-10 | AI Mentor Chat           | Question + context | AI                | Guidance          | Không làm hộ toàn bộ         |
| STU-11 | Upload Completed File    | File               | Scan + store      | Submission File   | Validate type                |
| STU-12 | Add Reflection           | Form               | Save              | Reflection        | Configurable                 |
| STU-13 | Submit Task              | Files + reflection | Validate          | Submission        | Ghi submitted_at             |
| STU-14 | View AI Feedback         | Evaluation         | Fetch             | Feedback          | AI label                     |
| STU-15 | View Mentor Feedback     | Review             | Fetch             | Feedback          | —                            |
| STU-16 | Resubmit                 | Revised files      | New submission    | Resubmission      | Revision state               |
| STU-17 | ePortfolio               | Student ID         | Aggregate         | Portfolio         | Student owns sharing         |
| STU-18 | Skill Progression        | Skills             | Aggregate         | Multi-skill chart | Không radar mặc định         |
| STU-19 | Career Suggestions       | Evidence           | Match             | Careers           | Explainable                  |
| STU-20 | Roadmap                  | Career direction   | Generate          | Roadmap           | Student editable             |

---

# 11. Student Task Flow

## Không có:

* Start Work button;
* Work Session tracking;
* Word-like Editor;
* internal document editing;
* autosave;
* track changes;
* typing log;
* version history nội bộ.

Flow:

```text
Mentor Assign
↓
Student Accept
↓
accepted_at
↓
Download Input
↓
Work Outside WORKLAB
↓
Optional AI Mentor
↓
Upload Completed File
↓
Add Reflection
↓
Submit
↓
submitted_at
↓
Calculate Elapsed Time
↓
AI Evaluation
↓
Mentor Review
```

---

# 12. Task Time Tracking

WORKLAB chỉ ghi:

* `assigned_at`;
* `accepted_at`;
* `submitted_at`;
* `completed_at`.

## Ý nghĩa

### assigned_at

Mentor giao task.

### accepted_at

Sinh viên xác nhận nhận task.

### submitted_at

Sinh viên submit file.

### completed_at

Task được đóng sau review.

---

## Example

```json
{
  "assigned_at": "2026-07-17T15:00:00+07:00",
  "accepted_at": "2026-07-18T09:00:00+07:00",
  "submitted_at": "2026-07-20T16:30:00+07:00"
}
```

Hiển thị:

> Hoàn thành sau 2 ngày 7 giờ 30 phút kể từ khi nhận task.

Không được hiển thị:

> Sinh viên đã làm 55,5 giờ.

---

## Constraint

Elapsed time không được dùng làm Skill Signal.

Không được suy luận:

* làm nhanh = giỏi;
* làm chậm = yếu;
* online lâu = chăm chỉ;
* submit muộn = thiếu động lực.

Chỉ dùng cho:

* deadline;
* overdue;
* task planning;
* estimated duration calibration.

---

# 13. TaskAssignment Entity

```json
{
  "assignment_id": "assignment_001",
  "task_id": "task_001",
  "assignee_type": "STUDENT",
  "assignee_id": "student_001",
  "status": "ACCEPTED",
  "assigned_at": "",
  "accepted_at": "",
  "due_at": "",
  "submitted_at": null,
  "completed_at": null
}
```

---

# 14. File Upload Requirements

## Input

```json
{
  "assignment_id": "assignment_001",
  "deliverable_id": "deliverable_001",
  "file": "<binary>"
}
```

## Output

```json
{
  "submission_file_id": "file_001",
  "assignment_id": "assignment_001",
  "deliverable_id": "deliverable_001",
  "file_name": "final_output.docx",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size_bytes": 248300,
  "uploaded_by": "student_001",
  "uploaded_at": "",
  "scan_status": "PASSED"
}
```

---

## Constraints

MVP mặc định:

```text
Max 50 MB / file
Max 10 files / submission
```

Configurable.

Có thể hỗ trợ:

* DOCX;
* PDF;
* XLSX;
* PPTX;
* ZIP;
* PNG/JPG;
* external link nếu task cho phép.

Security:

* MIME validation;
* virus scan;
* private storage;
* signed URL;
* permission check.

---

# 15. Submission Requirements

## Input

```json
{
  "assignment_id": "assignment_001",
  "deliverables": [
    {
      "deliverable_id": "deliverable_001",
      "submission_file_id": "file_001"
    }
  ],
  "student_reflection": {
    "challenge": "",
    "ai_usage": "",
    "changes_after_feedback": "",
    "remaining_uncertainty": []
  }
}
```

Backend:

```text
Validate assignment
↓
Validate required deliverables
↓
Validate file scan
↓
Create Submission
↓
Set submitted_at
↓
Calculate elapsed time
↓
Trigger AI Evaluation
```

Output:

```json
{
  "submission_id": "submission_001",
  "assignment_id": "assignment_001",
  "status": "SUBMITTED_TO_MENTOR",
  "accepted_at": "",
  "submitted_at": "",
  "elapsed_seconds": 199800
}
```

---

# 16. AI Mentor Requirements

## AI được phép

* giải thích thuật ngữ;
* giải thích khái niệm;
* đưa nhiều phương án;
* gợi ý phương pháp;
* kiểm tra consistency;
* giải thích yêu cầu task;
* trả lời câu hỏi;
* hỗ trợ reflection;
* giải thích feedback.

## AI không được phép

* submit thay student;
* xác nhận Evidence;
* nâng Skill Level;
* tạo career fit score;
* đánh giá tính cách;
* suy luận động lực;
* tự quyết định task pass/fail cuối cùng.

---

## AI Mentor Output

```json
{
  "response": "",
  "response_type": "GUIDANCE",
  "references": [],
  "confidence": "MEDIUM",
  "limitations": [],
  "requires_human_review": false
}
```

---

# 17. Activity Log

Vì Student làm task bên ngoài WORKLAB, log được đơn giản hóa.

## Log

```text
TASK_ASSIGNED
TASK_ACCEPTED

TASK_INPUT_DOWNLOADED

AI_HELP_REQUESTED

SUBMISSION_FILE_UPLOADED
SUBMISSION_FILE_REMOVED

FINAL_SUBMISSION_CREATED

MENTOR_FEEDBACK_RECEIVED

REVISION_REQUESTED
REVISION_FILE_UPLOADED
RESUBMISSION_CREATED

TASK_COMPLETED
```

Không log:

```text
KEY_PRESS
MOUSE_MOVE
TYPING_SPEED
TIME_ON_PAGE
CLICK_COUNT
WORK_SESSION
```

---

# 18. ActivityEvent Schema

```json
{
  "event_id": "evt_001",
  "actor_id": "student_001",
  "actor_type": "STUDENT",
  "task_id": "task_001",
  "assignment_id": "assignment_001",
  "event_type": "SUBMISSION_FILE_UPLOADED",
  "object_type": "FILE",
  "object_id": "file_001",
  "metadata": {},
  "created_at": ""
}
```

---

# 19. AI Evaluation Requirements

## Input

AI Evaluation sử dụng:

```text
Task Brief
+
Acceptance Criteria
+
Uploaded Final File
+
Student Reflection
+
Allowed AI Mentor Interactions
+
Previous Mentor Feedback
```

Không có:

* internal editing history;
* typing activity;
* detailed document version diff.

---

## Input Schema

```json
{
  "task_id": "task_001",
  "submission_id": "submission_001",
  "task_criteria": [],
  "submission_files": [],
  "student_reflection": {},
  "allowed_ai_interaction_refs": [],
  "previous_feedback_refs": []
}
```

---

## Output

```json
{
  "evaluation_id": "eval_001",
  "submission_id": "submission_001",
  "criteria_results": [
    {
      "criterion_id": "criterion_001",
      "status": "MEETS",
      "comment": "",
      "evidence_refs": []
    }
  ],
  "suggested_evidence_claims": [],
  "confidence": "MEDIUM",
  "missing_information": []
}
```

---

## Constraints

AI Evaluation luôn là:

```text
DRAFT
```

Mentor là người quyết định cuối.

Mọi nhận định phải có:

```text
evidence_refs
```

Không output:

* Personality Trait;
* Motivation Score;
* Career Success Probability;
* Career Fit Percentage.

---

# 20. Evidence Requirements

## Evidence Claim

```json
{
  "evidence_id": "evidence_001",
  "student_id": "student_001",
  "skill_id": "skill_001",
  "task_id": "task_001",
  "claim": "",
  "observed_actions": [],
  "evidence_sources": [
    "FINAL_OUTPUT",
    "STUDENT_REFLECTION",
    "AI_MENTOR_INTERACTION",
    "MENTOR_REVIEW"
  ],
  "task_complexity": "T1",
  "risk_level": "R0",
  "autonomy_level": "GUIDED",
  "proposed_skill_level": "L1",
  "status": "AI_DRAFT"
}
```

---

## Evidence State

```text
AI_DRAFT
↓
STUDENT_REVIEWED
↓
PENDING_MENTOR
↓
VERIFIED
```

Alternative:

```text
PENDING_MENTOR
→ NEED_MORE_EVIDENCE

PENDING_MENTOR
→ REJECTED
```

---

# 21. ePortfolio Requirements

## Student View

Hiển thị:

* profile summary;
* verified skills;
* verified evidence;
* task/project đã làm;
* mentor verification;
* skill progression;
* AI effort observations;
* career suggestions;
* suggested next tasks;
* privacy settings.

---

## Business View

Business View phải chuyên nghiệp hơn Student View.

Hiển thị:

* professional summary;
* verified skills;
* selected evidence;
* selected projects;
* task context;
* mentor verification;
* skill level;
* career interests nếu student share.

Không hiển thị:

* raw AI chat;
* private reflection;
* raw activity log;
* private mentor notes;
* disputed evidence.

Bắt buộc consent.

---

# 22. Skill Progression

Không dùng radar chart làm biểu đồ chính.

Sử dụng:

> Multi-skill progression chart

User có thể:

* search skill;
* select 1–8 skills;
* filter skill group;
* filter time;
* bật/tắt skill.

Input:

```json
{
  "skills": [
    {
      "skill_id": "skill_001",
      "name": "Legal Translation",
      "data_points": [
        {
          "date": "",
          "observed_level": "L1",
          "evidence_id": "evidence_001"
        }
      ]
    }
  ]
}
```

---

# 23. Career Suggestion

## Input

```text
Verified Skills
+
Evidence Context
+
Student-selected Interests
+
Market Job-Skill Mapping
```

## Output

```json
{
  "career_suggestions": [
    {
      "job_group_id": "job_001",
      "job_title": "Localization Specialist",
      "relation_reason": [
        "Sử dụng terminology management",
        "Sử dụng quality checking"
      ],
      "supported_skills": [],
      "skills_to_explore": [],
      "suggested_tasks": [],
      "market_signal": {},
      "confidence": "MEDIUM"
    }
  ]
}
```

Không có:

```text
Fit %
Best career
Success probability
Not suitable
```

---

# 24. Labor Market Requirements

Input:

* job postings;
* normalized titles;
* skills;
* region;
* salary;
* period;
* experience;
* education.

Output:

* trending jobs;
* trending skills;
* regional heatmap;
* skill demand;
* salary range;
* entry-level opportunities.

Mỗi Market Signal bắt buộc có:

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

---

# 25. Task State Machine

```text
DRAFT_UNSTRUCTURED
↓
AI_STRUCTURING
↓
ENTERPRISE_REVIEW
↓
PENDING_MENTOR_APPROVAL
↓
APPROVED
↓
ASSIGNED
↓
ACCEPTED
↓
SUBMITTED_TO_MENTOR
↓
MENTOR_REVIEW
↓
MENTOR_APPROVED
↓
SENT_TO_ENTERPRISE
↓
ENTERPRISE_REVIEW
↓
CLOSED
```

Không cần:

```text
IN_PROGRESS
```

Frontend coi:

```text
status = ACCEPTED
AND submitted_at = null
```

là:

> Đang thực hiện.

---

## Revision Flow

```text
MENTOR_REVIEW
↓
REVISION_REQUESTED
↓
RESUBMITTED_TO_MENTOR
↓
MENTOR_REVIEW
```

---

## Exception States

```text
NEED_MORE_INFORMATION
REJECTED
PAUSED
CANCELLED
```

Backend validate mọi transition.

---

# 26. Core Backend Entities

## Identity

```text
User
Role
Organization
BusinessProfile
MentorProfile
StudentProfile
Permission
Consent
```

---

## Task

```text
TaskConversation
TaskMessage
TaskBrief
TaskVariant
Task
TaskInput
TaskDeliverable
TaskCriterion
TaskCheckpoint
TaskSkillRequirement
TaskReview
TaskAssignment
```

---

## Team

```text
Team
TeamMember
```

---

## File & Submission

```text
UploadedFile
Submission
SubmissionDeliverable
```

---

## AI

```text
AIInteraction
AIEvaluation
```

---

## Review

```text
MentorReview
EnterpriseReview
Feedback
Revision
```

---

## Evidence

```text
EvidenceClaim
EvidenceVerification
```

---

## Skill

```text
SkillFramework
Skill
SkillLevelRubric
StudentSkillState
```

---

## Career

```text
JobGroup
JobSkillRequirement
CareerDirection
CareerSuggestion
LearningRoadmap
RoadmapItem
DraftTask
```

---

## Market

```text
MarketJobPosting
MarketJobGroup
MarketSkill
RegionalMarketSnapshot
RegionalSkillSignal
MarketDataSource
```

---

## System

```text
Notification
AuditLog
Consent
Permission
ActivityEvent
```

---

# 27. Entities không cần trong MVP

Không cần:

```text
WorkSession
InternalDocumentEditor
RichTextOperation
AutosaveVersion
EditHistory
InternalDocumentVersion
```

---

# 28. Non-Functional Requirements

| ID     | Category        | Requirement      | Target                  |
| ------ | --------------- | ---------------- | ----------------------- |
| NFR-01 | Performance     | Normal API       | P95 < 500ms             |
| NFR-02 | Dashboard       | Aggregate load   | < 2s                    |
| NFR-03 | AI              | Initial response | mục tiêu < 5s           |
| NFR-04 | Availability    | MVP uptime       | ≥99.5%                  |
| NFR-05 | Security        | Password         | Hashed                  |
| NFR-06 | Security        | File storage     | Encrypted               |
| NFR-07 | Transport       | API              | HTTPS/TLS               |
| NFR-08 | Authorization   | Access           | RBAC                    |
| NFR-09 | Privacy         | ePortfolio       | Consent based           |
| NFR-10 | Auditability    | Decision         | Audit log               |
| NFR-11 | Explainability  | AI Evaluation    | Evidence refs           |
| NFR-12 | AI Safety       | Final decision   | Human                   |
| NFR-13 | Accessibility   | UI               | WCAG AA target          |
| NFR-14 | Localization    | UI               | Vietnamese-first        |
| NFR-15 | Observability   | Backend          | Central logging         |
| NFR-16 | File security   | Upload           | Malware scan            |
| NFR-17 | Idempotency     | Submit/Approve   | Required                |
| NFR-18 | Data integrity  | State transition | Transaction-safe        |
| NFR-19 | AI traceability | AI generation    | Model/prompt reference  |
| NFR-20 | Responsive      | Business/Mentor  | Desktop-first           |
| NFR-21 | Responsive      | Student          | Desktop + mobile/tablet |

---

# 29. AI Traceability

Mỗi AI output nên lưu:

```json
{
  "model_id": "",
  "model_version": "",
  "prompt_template_id": "",
  "input_refs": [],
  "created_at": "",
  "confidence": ""
}
```

Human-in-the-loop:

```text
AI proposes Task
→ Mentor approves

AI proposes Evaluation
→ Mentor reviews

AI proposes Evidence
→ Mentor verifies

AI suggests Career
→ Student decides
```

---

# 30. Frontend Branding

Phải phân biệt rõ:

```text
WORKLAB for Business
WORKLAB for Mentor
WORKLAB for Student
```

Indicator:

| Type                  | Color        |
| --------------------- | ------------ |
| Urgent / Error        | Red          |
| Warning               | Orange/Amber |
| Success / Verified    | Green        |
| Information / Primary | Blue         |
| Pending / Neutral     | Gray         |

Layout tổng thể dùng ít màu.

Màu mạnh chỉ dùng cho:

* urgent;
* deadline;
* risk;
* warning;
* success;
* verification;
* action chính.

---

# 31. Student Navigation

Sidebar phải thống nhất trên toàn bộ Student App:

```text
Trang chủ
Cơ hội thị trường
Nhiệm vụ
ePortfolio
Lộ trình học tập
```

Không thay đổi sidebar giữa Assignment và ePortfolio.

---

# 32. Business Navigation

```text
Tổng quan
Tạo nhiệm vụ
Nhiệm vụ
Ứng viên
ePortfolio đã chia sẻ
```

---

# 33. Mentor Navigation

```text
Tổng quan
Thị trường lao động
Nhiệm vụ
Sinh viên
Xác nhận bằng chứng
Lộ trình
```

---

# 34. Free Task Policy

Mặc định:

```text
Task Posting = FREE
```

Doanh nghiệp không phải trả tiền cho phần lớn task.

Task miễn phí phải:

* có giá trị học tập;
* giới hạn T1–T3;
* giới hạn R0–R1;
* được mentor duyệt;
* không thay thế nhân viên;
* không có yêu cầu SLA thương mại;
* không mặc định chuyển quyền sở hữu output.

---

## Learning-only Task

Doanh nghiệp:

* có thể xem output;
* có thể feedback;
* không được mặc định sử dụng production.

Đây là loại ưu tiên MVP.

---

## Optional Business Use

Nếu doanh nghiệp muốn sử dụng output:

* cần student consent;
* cần xác định IP;
* có thể cần compensation;
* mentor phải duyệt.

Không tự động.

---

# 35. MVP Acceptance Criteria

## Business

* [ ] Tạo brief qua AI Chat.
* [ ] Upload task input.
* [ ] AI tạo structured task.
* [ ] AI đề xuất T-level.
* [ ] AI đề xuất R-level.
* [ ] Business chọn variant.
* [ ] Gửi task.

## Mentor

* [ ] Nhận task.
* [ ] Xem brief gốc.
* [ ] Xem AI rationale.
* [ ] Approve/Reject.
* [ ] Assign student/team.

## Student

* [ ] Xem task.
* [ ] Accept task.
* [ ] `accepted_at` được lưu.
* [ ] Download input.
* [ ] Chat AI Mentor.
* [ ] Upload completed file.
* [ ] Add reflection.
* [ ] Submit.
* [ ] `submitted_at` được lưu.

## Assessment

* [ ] AI đọc output.
* [ ] AI tạo draft evaluation.
* [ ] Mentor review.
* [ ] Mentor request revision hoặc approve.
* [ ] Mentor verify Evidence.

## Business Result

* [ ] Business xem final output.
* [ ] Business xem mentor feedback.
* [ ] Business gửi feedback.

## ePortfolio

* [ ] Verified Evidence xuất hiện.
* [ ] Skill Progression cập nhật.
* [ ] Career Suggestions cập nhật.
* [ ] Suggested Next Task được tạo.

---

# 36. Out of Scope — MVP

Không xây:

* Expert Reviewer.
* T4–T5.
* R2–R3.
* Word-like Editor.
* Internal document editing.
* Start Work tracking.
* WorkSession tracking.
* Keystroke tracking.
* Autosave editor.
* Full document version history.
* Automated final Skill Level.
* Career fit percentage.
* Student ranking.
* Open freelance marketplace.
* Pay-per-task marketplace.
* Commission từ lao động sinh viên.
* Certification chính thức.
* ATS đầy đủ.
* Labor Market forecasting dài hạn.
* Deep LMS integration.

---

# 37. Definition of Done — Backend

Một feature Backend Done khi:

* schema rõ;
* API contract rõ;
* validation đầy đủ;
* permission check;
* state transition validate;
* audit log;
* error handling;
* idempotency khi cần;
* test business rules.

---

# 38. Definition of Done — AI

AI feature Done khi:

* input schema rõ;
* output schema structured;
* có confidence;
* có limitation;
* có fallback;
* traceable;
* không tự final decision;
* user/mentor có thể reject;
* có evaluation dataset cơ bản.

---

# 39. Definition of Done — Frontend

Frontend feature Done khi có:

* loading state;
* empty state;
* error state;
* permission denied;
* insufficient data;
* success state;
* responsive;
* status indicator đúng;
* AI-generated label;
* action tiếp theo rõ ràng.

---

# 40. Nguyên tắc chung cho 3 team

> **Backend giữ đúng dữ liệu, trạng thái và quyền truy cập.**

> **AI tạo đề xuất có căn cứ nhưng không ra quyết định cuối.**

> **Frontend phải làm rõ dữ liệu nào do AI đề xuất, dữ liệu nào do con người xác nhận và ai đang chịu trách nhiệm cho hành động tiếp theo.**

Workflow quan trọng nhất:

```text
AI proposes
→ Human reviews
→ System records
→ Student owns evidence
```

Và MVP Student Task được chốt thành:

```text
Accept Task
→ accepted_at
→ Download Input
→ Work Outside WORKLAB
→ Optional AI Mentor
→ Upload Completed File
→ Submit
→ submitted_at
→ AI Evaluation
→ Mentor Review
→ Verified Evidence
→ ePortfolio
```

Đây là phiên bản requirement tổng hợp nên dùng làm **source of truth ban đầu cho Backend, AI và Frontend**.
