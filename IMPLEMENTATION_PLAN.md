# Comprehensive Implementation Plan: Career Guidance System

This document outlines the technical architecture, design patterns, and implementation roadmap for the Backend team, focusing on **Dev 1 (Market Data)** and **Dev 3 (Guidance & AI)**, integrated with **Dev 2 (Student Profile)**.

## 🏗️ 1. Architecture & Folder Structure

We adopt a **Domain-Driven Design (DDD)** approach combined with a **Layered Architecture** to ensure the system is maintainable, scalable, and follows **SOLID** principles.

### Directory Structure
```text
app/
├── main.py                 # Entry point: FastAPI initialization, router aggregation, middleware
├── core/                   # Shared system configuration
│   ├── config.py           # Pydantic Settings (Env var management)
│   ├── database.py         # SQLAlchemy engine, SessionLocal, Base
│   ├── security.py         # JWT, Password hashing
│   └── exceptions.py       # Custom business exceptions (e.g., BusinessLogicException)
├── domains/                # Business Domains
│   ├── market/             # [DEV 1] Market Data Domain
│   │   ├── models.py       # SQLAlchemy Models (Skill, Career, JobPosting, JobSkill, CareerSkill)
│   │   ├── schemas.py      # Pydantic Schemas (Request/Response)
│   │   ├── repository.py   # DB Access Layer (SQLAlchemy queries)
│   │   ├── service.py      # Business Logic (Trend calculation, signal extraction)
│   │   └── router.py       # API Endpoints (HTTP Layer)
│   ├── student/            # [DEV 2] Student Profile Domain
│   │   ├── models.py       # Student, InteractionLog
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py      # AI Profile Builder logic
│   │   └── router.py
│   └── guidance/           # [DEV 3] Guidance & Recommendation Domain
│       ├── models.py       # EducationPath, Recommendation
│       ├── schemas.py
│       ├── repository.py
│       ├── service.py      # Recommendation Engine logic
│       ├── anti_bias.py    # Ethics/Anti-bias logic (Strategy Pattern)
│       └── router.py
└── tests/                  # Testing Suite
    ├── conftest.py         # Pytest fixtures
    ├── unit/               # Logic tests (e.g., AntiBiasValidator)
    └── integration/        # API flow tests (Router -> Service -> DB)
```

> **Wiring rule**: `main.py` is the only place allowed to know about every domain. It must `include_router()` each domain's `router.py` and import each domain's `models.py` (even domains with no router yet) so `Base.metadata` sees every table before `create_all()` runs. A domain that exists under `domains/` but isn't imported/registered here is dead code — this bit the project once (Sprint 1/2 code was written but never mounted onto the running app) and is why this rule is called out explicitly.

---

## 🛠️ 2. OOP Design & SOLID Principles

### Layer Responsibilities (SRP)
- **Router Layer**: Handles HTTP requests, validates input via Pydantic, and returns responses. No business logic.
- **Service Layer**: Orchestrates business logic, coordinates between repositories, and interacts with AI clients.
- **Repository Layer**: Pure data access. Isolates SQL queries from business logic (**Dependency Inversion**).
- **Model Layer**: Defines the database schema.

### Design Patterns
- **Strategy Pattern (Anti-Bias)**: 
  - An abstract `BiasValidator` base class is defined. 
  - Specific validators (`DiversityValidator`, `RegionExpansionValidator`) implement the `validate()` method.
  - `AntiBiasEngine` executes a list of validators, allowing new rules to be added without modifying existing logic (**Open/Closed Principle**).
- **Dependency Injection (DI)**: 
  - DB sessions and AI clients are injected into services via FastAPI's `Depends`, making the code highly testable.

---

## 👨‍💻 3. Dev 1: Market Data Implementation

**Goal:** Extract real skill demand signals from job market data — including salary, regional demand, and change over time — and surface which careers are growing and which skills are locally scarce.

### Technical Specifications
- **Models**: `Skill`, `Career` (with `market_trend` Enum, linked to `Skill` via `CareerSkill`), `JobPosting` (with `salary_min`/`salary_max` and an indexed `posted_at`), `JobSkill` (Association).
  - `Career` <-> `Skill` (`career_skills` table) is what makes trend calculation possible: a career's demand signal is derived from the job-posting activity of *its* linked skills, not from string-matching job titles.
- **Key Features**:
    - **Bulk Ingestion**: `POST /jobs/bulk` uses a SQLAlchemy 2.0 Core `insert(JobPosting).returning(JobPosting.id)` executemany, followed by a single bulk `insert(JobSkill)` for the associations — two statements total regardless of batch size, instead of a per-row `add()`/`flush()` loop. (Classic `session.bulk_insert_mappings()` doesn't return generated PKs, which are needed to populate `JobSkill`, so Core `insert().returning()` is the correct 2.0-style equivalent.)
    - **Historical backfill**: `JobPostingCreate.posted_at` is optional and accepted from the client — real tuyển dụng datasets can be ingested with their true publish dates instead of all collapsing to "now", which is what makes time-based trend analysis meaningful.
    - **Signal Extraction**: 
      - `GET /analytics/skill-demand?location=&days=` — skill frequency for a location, optionally windowed to the last N days.
      - `GET /analytics/skill-trend?location=&window_days=30` — compares each skill's demand across two equal back-to-back windows and returns `{demand_recent, demand_previous, growth_rate}`, giving the "xu hướng theo thời gian" and per-region shortage signal the requirements ask for.
    - **Trend Automation**: `POST /jobs/bulk` schedules `MarketService.update_market_trends` as a FastAPI `BackgroundTask` after ingestion. For every `Career`, it sums job-posting counts (via its linked skills) over the last 30 days vs. the prior 30 days; growth ≥ +15% → `RISING`, ≤ -15% → `DECLINING`, otherwise `STABLE`. A career with no linked skills is left untouched rather than defaulted, since there's no signal to compute from.

---

## 👩‍💻 4. Dev 3: Guidance & Recommendation Implementation

**Goal:** Synthesize student profiles and market trends into ethical, explainable recommendations.

### Technical Specifications
- **Models**: `EducationPath` (University/Vocational/Short-course), `Recommendation` (linked to Student and Path).
- **Recommendation Pipeline**:
    1. **Data Fetch**: Retrieve `ai_inferred_profile` (Dev 2) and `market_trend` (Dev 1).
    2. **AI Generation**: Prompt LLM to suggest paths with a mandatory `reasoning_explanation` (**Explainability**).
    3. **Anti-Bias Validation**: 
       - **Diversity**: Force a mix of academic and vocational paths.
       - **Expansion**: Inject remote/inter-city opportunities for students in restricted locations.
    4. **Persistence**: Store validated recommendations in the DB.

---

## 🤝 5. Integration Contract

| Provider | Consumer | Data Object | Format | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Dev 1** | **Dev 3** | `MarketSignal` | `{career_id, trend, demand_score}` | Market context for AI. |
| **Dev 2** | **Dev 3** | `StudentProfile` | `{student_id, inferred_traits, skills[]}` | Personalization for AI. |
| **Dev 3** | **Dev 2** | `RecLink` | `{student_id, recommendation_id}` | Linking guidance to profile. |

`trend` comes straight from `Career.market_trend` (`GET /market/careers/`); `demand_score` should be sourced from `GET /market/analytics/skill-trend` for the student's `location`, keyed by the skills linked to that career — Dev 3 hasn't consumed this yet, so keep the shape in sync with `SkillDemandTrend` when that integration lands.

---

## 🧪 6. Test Plan (Testing Pyramid)

### Unit Tests (70%)
- **Focus**: Pure logic in `service.py` and `anti_bias.py`.
- **Key Case**: Verify `DiversityValidator` converts a "University-only" list into a mixed list.

### Integration Tests (20%)
- **Focus**: API endpoints $\rightarrow$ Service $\rightarrow$ DB.
- **Key Case**: `POST /jobs/bulk` correctly populates the database and triggers background trend updates.

### E2E & AI Evaluation (10%)
- **Focus**: Full user flow and AI output quality.
- **AI Eval**: Use "LLM-as-a-judge" (e.g., GPT-4) to score `reasoning_explanation` on logic and personalization.

---

## 📖 7. Swagger & Documentation
- **Grouping**: Use `tags` to separate `Market Data`, `Student Profile`, and `AI Guidance`.
- **Metadata**: Every endpoint must have a `summary`, `description`, and `response_model`.
- **Examples**: Pydantic fields must include `examples` for rapid frontend testing.

---

## 🚀 8. Implementation Roadmap

| Sprint | Focus | Dev 1 (Market) | Dev 2 (Student) | Dev 3 (Guidance) |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | **Core Base** | Models, CRUD for Skill/Career. | Models, CRUD for Student. | Models, CRUD for EducationPath. |
| **Sprint 2** | **Logic & Data** | Bulk Ingestion, Skill Demand API. | Interaction Logs, JSON Profile. | Mapping Career $\rightarrow$ Path. |
| **Sprint 3** | **AI & Ethics** | Optimize Market Signals for AI. | AI Profile Generator. | Recommendation Engine + Anti-Bias. |
