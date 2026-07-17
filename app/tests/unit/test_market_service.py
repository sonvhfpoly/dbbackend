import pytest
from datetime import date
from domains.market.service import MarketService
from domains.market.models import MarketTrend, SeniorityLevel
from domains.market.schemas import JobPostingCreate

def make_service(repo=None):
    """MarketService.__init__ opens a real DB session via MarketRepository(db) —
    bypass it and inject a fake repo directly, so this stays a pure-logic test."""
    service = object.__new__(MarketService)
    service.repo = repo
    return service

class FakeRepo:
    """Minimal in-memory stand-in for MarketRepository, covering only what
    update_market_trends/get_market_overview/ingest_jobs actually call."""

    def __init__(self, job_skill_ids=None, job_career_map=None, skill_count_queue=None,
                 overview_values=None):
        self.job_skill_ids = job_skill_ids or {}
        self.job_career_map = job_career_map or {}
        self._skill_count_queue = list(skill_count_queue or [])
        self.job_trends = {}
        self.career_trends = {}
        self.created_rows = []
        self._overview_values = overview_values or {}
        # count_job_postings is called twice per get_market_overview (current
        # window, then previous window) — pop values off this queue in order.
        self._job_postings_queue = list(self._overview_values.get("job_postings_queue", []))

    # ---- ingest_jobs dependencies ----
    def get_job_skill_sets(self):
        return {job_id: set(ids) for job_id, ids in self.job_skill_ids.items()}

    def get_career_general_skill_sets(self):
        return {}

    def get_job_career_map(self):
        return dict(self.job_career_map)

    def bulk_create_jobs(self, rows):
        self.created_rows.extend(rows)
        return len(rows)

    # ---- update_market_trends dependencies ----
    def get_all_job_ids(self):
        return list(self.job_skill_ids.keys())

    def get_job_skill_ids(self, job_id):
        return list(self.job_skill_ids.get(job_id, []))

    def get_job_count_for_skills(self, skill_ids, start, end):
        return self._skill_count_queue.pop(0)

    def update_job_trend(self, job_id, trend):
        self.job_trends[job_id] = trend

    def update_career_trend(self, career_id, trend):
        self.career_trends[career_id] = trend

    # ---- get_market_overview dependencies ----
    def count_job_postings(self, **kwargs):
        return self._job_postings_queue.pop(0)

    def count_distinct_jobs_with_postings(self, **kwargs):
        return self._overview_values.get("job_group_count", 0)

    def count_distinct_skills_demanded(self, **kwargs):
        return self._overview_values.get("skill_count", 0)

    def get_last_posting_timestamp(self, **kwargs):
        return self._overview_values.get("last_posting_at")

    def get_weekly_posting_counts(self, **kwargs):
        return self._overview_values.get("weekly_counts", [])

    def get_yearly_average_weekly_count(self, **kwargs):
        return self._overview_values.get("yearly_avg", 0.0)

    def get_location_distribution(self, **kwargs):
        return self._overview_values.get("location_rows", [])

# ---- _resolve_job_id ----

def test_resolve_job_id_picks_best_skill_overlap():
    job_skill_map = {1: {10, 11, 12}, 2: {13, 14}}
    result = MarketService._resolve_job_id([10, 11, 99], job_skill_map)
    assert result == 1  # 2 shared skills vs 0 for job 2

def test_resolve_job_id_returns_none_when_no_overlap():
    job_skill_map = {1: {10, 11}, 2: {13, 14}}
    result = MarketService._resolve_job_id([99, 100], job_skill_map)
    assert result is None

# ---- _resolve_career_id_fallback (beginner case) ----

def test_resolve_career_id_fallback_matches_general_skills():
    career_general_skill_map = {1: {50, 51}}
    result = MarketService._resolve_career_id_fallback([50, 999], career_general_skill_map)
    assert result == 1

def test_resolve_career_id_fallback_returns_none_when_no_match():
    career_general_skill_map = {1: {50, 51}}
    result = MarketService._resolve_career_id_fallback([999], career_general_skill_map)
    assert result is None

# ---- _infer_seniority_levels ----

def test_infer_seniority_levels_matches_keyword():
    assert MarketService._infer_seniority_levels("Senior Backend Developer") == [SeniorityLevel.SENIOR]

def test_infer_seniority_levels_defaults_to_mid_when_no_keyword():
    assert MarketService._infer_seniority_levels("Backend Developer") == [SeniorityLevel.MID]

def test_infer_seniority_levels_can_match_multiple_keywords():
    levels = MarketService._infer_seniority_levels("Junior/Fresher Backend Developer")
    assert set(levels) == {SeniorityLevel.JUNIOR}  # both keywords map to the same level, no duplicate

# ---- _expand_and_resolve: core resolution + multi-level fan-out ----

def test_expand_and_resolve_fans_out_multiple_seniority_levels_into_separate_rows():
    service = make_service()
    jobs_data = [{"title": "DevOps (Junior/Mid)", "skill_ids": [], "seniority_levels": [SeniorityLevel.JUNIOR, SeniorityLevel.MID]}]

    rows = service._expand_and_resolve(jobs_data, job_skill_map={}, career_general_skill_map={}, job_career_map={})

    assert len(rows) == 2
    assert {r["seniority_level"] for r in rows} == {SeniorityLevel.JUNIOR, SeniorityLevel.MID}

def test_expand_and_resolve_resolves_job_id_and_derives_career_id_from_it():
    service = make_service()
    jobs_data = [{"title": "Backend Developer", "skill_ids": [10, 11], "seniority_levels": [SeniorityLevel.MID]}]
    job_skill_map = {5: {10, 11}}
    job_career_map = {5: 1}

    rows = service._expand_and_resolve(jobs_data, job_skill_map, career_general_skill_map={}, job_career_map=job_career_map)

    assert rows[0]["job_id"] == 5
    assert rows[0]["career_id"] == 1  # derived from the resolved job, not the fallback path

def test_expand_and_resolve_beginner_posting_falls_back_to_career_without_a_job():
    """The case this whole 2-tier heuristic exists for: a posting with only
    generic skills (no job-specific ones) still gets attributed to the right
    Career even though it can't be pinned to a specific Job."""
    service = make_service()
    jobs_data = [{"title": "Thuc Tap Sinh", "skill_ids": [50], "seniority_levels": [SeniorityLevel.INTERN]}]
    job_skill_map = {5: {10, 11}}  # no overlap with skill_ids=[50]
    career_general_skill_map = {1: {50, 51}}

    rows = service._expand_and_resolve(jobs_data, job_skill_map, career_general_skill_map, job_career_map={5: 1})

    assert rows[0]["job_id"] is None
    assert rows[0]["career_id"] == 1

def test_expand_and_resolve_respects_explicit_job_id_and_career_id_overrides():
    service = make_service()
    jobs_data = [{"title": "Backend Developer", "skill_ids": [10, 11], "job_id": 99, "career_id": 42,
                  "seniority_levels": [SeniorityLevel.MID]}]
    job_skill_map = {5: {10, 11}}  # would otherwise resolve to job_id=5

    rows = service._expand_and_resolve(jobs_data, job_skill_map, career_general_skill_map={}, job_career_map={5: 1})

    assert rows[0]["job_id"] == 99
    assert rows[0]["career_id"] == 42

def test_expand_and_resolve_leaves_both_none_when_nothing_matches():
    service = make_service()
    jobs_data = [{"title": "Unmatched Posting", "skill_ids": [999], "seniority_levels": [SeniorityLevel.MID]}]

    rows = service._expand_and_resolve(jobs_data, job_skill_map={5: {10}}, career_general_skill_map={1: {50}}, job_career_map={5: 1})

    assert rows[0]["job_id"] is None
    assert rows[0]["career_id"] is None

# ---- _classify_trend ----

def test_classify_trend_rising_above_threshold():
    assert MarketService._classify_trend(recent=12, previous=10) == MarketTrend.RISING  # +20%

def test_classify_trend_declining_below_threshold():
    assert MarketService._classify_trend(recent=8, previous=10) == MarketTrend.DECLINING  # -20%

def test_classify_trend_stable_within_threshold():
    assert MarketService._classify_trend(recent=10, previous=10) == MarketTrend.STABLE

def test_classify_trend_zero_baseline_with_demand_is_rising():
    assert MarketService._classify_trend(recent=3, previous=0) == MarketTrend.RISING

def test_classify_trend_zero_baseline_no_demand_is_stable():
    assert MarketService._classify_trend(recent=0, previous=0) == MarketTrend.STABLE

# ---- update_market_trends: Job-level + Career-level rollup ----

def test_update_market_trends_computes_job_trend_and_rolls_up_to_career():
    repo = FakeRepo(
        job_skill_ids={5: [10, 11]},
        job_career_map={5: 1},
        # First pair of calls is for Job 5 (recent, previous), second pair is
        # the Career-level rollup using the same unioned skill set.
        skill_count_queue=[12, 10, 12, 10],
    )
    service = make_service(repo)

    service.update_market_trends(window_days=30)

    assert repo.job_trends[5] == MarketTrend.RISING  # (12-10)/10 = 20%
    assert repo.career_trends[1] == MarketTrend.RISING

def test_update_market_trends_skips_jobs_with_no_linked_skills():
    repo = FakeRepo(job_skill_ids={5: []}, job_career_map={5: 1})
    service = make_service(repo)

    service.update_market_trends(window_days=30)  # must not raise or query counts

    assert 5 not in repo.job_trends

# ---- _confidence_for_sample / _growth_speed_for_rate ----

def test_confidence_for_sample_buckets():
    assert MarketService._confidence_for_sample(500) == "HIGH"
    assert MarketService._confidence_for_sample(100) == "MEDIUM"
    assert MarketService._confidence_for_sample(99) == "LOW"

def test_growth_speed_for_rate_buckets():
    assert MarketService._growth_speed_for_rate(0.30) == "STRONG"
    assert MarketService._growth_speed_for_rate(0.15) == "MODERATE"
    assert MarketService._growth_speed_for_rate(0.0) == "STABLE"
    assert MarketService._growth_speed_for_rate(-0.20) == "DECLINING"

def test_growth_speed_for_rate_none_is_stable():
    assert MarketService._growth_speed_for_rate(None) == "STABLE"

# ---- _to_location_shares ----

def test_to_location_shares_buckets_remainder_into_khu_vuc_khac():
    rows = [("Ho Chi Minh City", 50), ("Ha Noi", 30), ("Da Nang", 10), ("Can Tho", 5), ("Hue", 5)]

    shares = MarketService._to_location_shares(rows, top_n=3)

    assert [s["location"] for s in shares] == ["Ho Chi Minh City", "Ha Noi", "Da Nang", "Khu vuc khac"]
    assert shares[-1]["count"] == 10  # Can Tho (5) + Hue (5)
    assert round(sum(s["percent"] for s in shares), 1) == 100.0

def test_to_location_shares_empty_when_no_postings():
    assert MarketService._to_location_shares([], top_n=3) == []

def test_to_location_shares_omits_other_bucket_when_top_n_covers_everything():
    rows = [("Ho Chi Minh City", 10)]
    shares = MarketService._to_location_shares(rows, top_n=3)
    assert len(shares) == 1
    assert shares[0]["percent"] == 100.0

# ---- get_market_overview: end-to-end aggregate shape ----

def test_get_market_overview_combines_stats_chart_and_location_distribution():
    repo = FakeRepo(overview_values={
        "job_postings_queue": [25, 20],  # current window, then previous window
        "job_group_count": 3,
        "skill_count": 8,
        "weekly_counts": [(date(2026, 7, 6), 4), (date(2026, 7, 13), 6)],
        "yearly_avg": 2.5,
        "location_rows": [("Ho Chi Minh City", 15), ("Ha Noi", 10)],
    })
    service = make_service(repo)

    overview = service.get_market_overview(days=30)

    assert overview["stats"]["total_job_postings"] == 25
    assert overview["stats"]["mom_growth_rate"] == pytest.approx(0.25)  # (25-20)/20
    assert overview["stats"]["job_group_count"] == 3
    assert overview["stats"]["skill_count"] == 8
    assert overview["stats"]["confidence"] == "LOW"
    assert overview["stats"]["growth_speed"] == "MODERATE"  # 0.25 growth is between MODERATE (0.15) and STRONG (0.30)
    assert overview["chart"]["yearly_average_weekly_count"] == 2.5
    assert len(overview["chart"]["weekly_counts"]) == 2
    assert overview["location_distribution"][0]["location"] == "Ho Chi Minh City"

def test_get_market_overview_handles_zero_previous_count_as_null_growth():
    repo = FakeRepo(overview_values={"job_postings_queue": [5, 0]})
    service = make_service(repo)

    overview = service.get_market_overview(days=30)

    assert overview["stats"]["mom_growth_rate"] is None
    assert overview["stats"]["growth_speed"] == "STABLE"

# ---- ingest_jobs: thin wrapper over _expand_and_resolve + bulk_create_jobs ----

def test_ingest_jobs_resolves_job_id_and_persists_rows():
    repo = FakeRepo(job_skill_ids={5: [10, 11]}, job_career_map={5: 1})
    service = make_service(repo)
    posting = JobPostingCreate(
        title="Backend Developer", company="Acme", location="Ha Noi",
        description="desc", skill_ids=[10, 11],
    )

    count = service.ingest_jobs([posting])

    assert count == 1
    assert repo.created_rows[0]["job_id"] == 5
    assert repo.created_rows[0]["career_id"] == 1
