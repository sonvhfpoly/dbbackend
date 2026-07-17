"""Static sample dataset for the /market/seed-demo-data endpoint.

Job posting `days_ago` values are deliberately chosen so that, once ingested,
`MarketService.update_market_trends` (30-day growth window) produces a mix of
RISING / STABLE / DECLINING jobs, and so that some skills are visibly
concentrated in a few locations only (a shortage signal for the rest).

Hierarchy: 1 Career (industry) -> several Jobs (specific job families) ->
many JobPostings. `job_id`/`career_id` on each posting below are intentionally
NOT hard-coded — MarketService.seed_demo_data() resolves them through the same
_expand_and_resolve heuristic real ingestion uses, so the demo proves the
classification logic actually works instead of just asserting it does.
"""

# Categories use this DB's lowercase ck_skills_category vocabulary
# (technical/data/ai/product/design/business/soft_skill/general) — an
# out-of-band constraint on the live skills table, not part of this
# SQLAlchemy model (Skill.category is a plain string, unconstrained here).
SEED_SKILLS = [
    {"name": "Python", "category": "technical"},
    {"name": "JavaScript", "category": "technical"},
    {"name": "React", "category": "technical"},
    {"name": "SQL", "category": "data"},
    {"name": "Docker", "category": "technical"},
    {"name": "Kubernetes", "category": "technical"},
    {"name": "AWS Cloud", "category": "technical"},
    {"name": "Machine Learning", "category": "ai"},
    {"name": "Excel", "category": "business"},
    {"name": "English Communication", "category": "soft_skill"},
    # General/foundational skills — linked to the Career (industry), not to any
    # one Job, so a beginner posting that only lists these can still be
    # attributed to the right industry via the CareerSkill fallback.
    {"name": "Toan hoc", "category": "general"},
    {"name": "Giai quyet van de", "category": "general"},
    {"name": "Tu duy logic", "category": "general"},
]

# The broadest grouping ("nganh") — every seed Job below belongs to this one.
SEED_CAREER = {"title": "Cong nghe thong tin"}

# General/foundational skills attached directly to the Career (not any Job) —
# the beginner-posting fallback signal.
SEED_GENERAL_SKILLS = ["Toan hoc", "Giai quyet van de", "Tu duy logic"]

# Specific job families ("nghe cu the") within the Career above.
SEED_JOBS = [
    {"title": "Backend Developer", "skills": ["Python", "SQL", "Docker"]},
    {"title": "Frontend Developer", "skills": ["JavaScript", "React"]},
    {"title": "Data Scientist", "skills": ["Python", "Machine Learning", "SQL"]},
    {"title": "DevOps Engineer", "skills": ["Docker", "Kubernetes", "AWS Cloud"]},
    {"title": "Business Analyst", "skills": ["Excel", "SQL", "English Communication"]},
]

# location: Ho Chi Minh City / Ha Noi have broad coverage; Da Nang and Can Tho
# each miss whole skill clusters on purpose, to demonstrate a regional gap.
SEED_JOB_POSTINGS = [
    # --- DevOps Engineer (Docker/Kubernetes/AWS Cloud) -> RISING: 2 previous, 6 recent ---
    {"title": "DevOps Engineer", "company": "CloudViet", "location": "Ho Chi Minh City", "days_ago": 50,
     "salary_min": 20_000_000, "salary_max": 30_000_000, "skills": ["Docker", "AWS Cloud"],
     "seniority_levels": ["MID"]},
    {"title": "SRE Engineer", "company": "TechCorp", "location": "Ha Noi", "days_ago": 35,
     "salary_min": 25_000_000, "salary_max": 35_000_000, "skills": ["Kubernetes", "Docker"],
     "seniority_levels": ["SENIOR"]},
    {"title": "DevOps Engineer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 3,
     "salary_min": 22_000_000, "salary_max": 32_000_000, "skills": ["Docker", "Kubernetes", "AWS Cloud"],
     "seniority_levels": ["MID"],
     "requirements": "2+ nam kinh nghiem voi Docker/Kubernetes, hieu biet ve CI/CD.",
     "benefits": "Bao hiem suc khoe cao cap, lam viec hybrid, thuong hieu suat quy."},
    {"title": "Cloud Engineer", "company": "CloudViet", "location": "Ho Chi Minh City", "days_ago": 7,
     "salary_min": 20_000_000, "salary_max": 28_000_000, "skills": ["AWS Cloud", "Docker"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "Site Reliability Engineer", "company": "TechCorp", "location": "Ha Noi", "days_ago": 10,
     "salary_min": 25_000_000, "salary_max": 38_000_000, "skills": ["Kubernetes", "Docker"],
     "seniority_levels": ["SENIOR"]},
    {"title": "DevOps Engineer", "company": "StartupY", "location": "Ha Noi", "days_ago": 14,
     "salary_min": 18_000_000, "salary_max": 26_000_000, "skills": ["Docker", "AWS Cloud"],
     "seniority_levels": ["MID"]},
    {"title": "Platform Engineer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 18,
     "salary_min": 24_000_000, "salary_max": 34_000_000, "skills": ["Kubernetes", "AWS Cloud"],
     "seniority_levels": ["SENIOR"]},
    {"title": "DevOps Engineer", "company": "LogiTech", "location": "Ho Chi Minh City", "days_ago": 22,
     "salary_min": 20_000_000, "salary_max": 30_000_000, "skills": ["Docker", "Kubernetes"],
     "seniority_levels": ["MID"]},
    # Multi-level source ad ("Junior/Mid DevOps") — service fans this out into
    # 2 separate JobPosting rows (one per level) at ingest/seed time.
    {"title": "DevOps Engineer (Junior/Mid)", "company": "CloudViet", "location": "Da Nang", "days_ago": 2,
     "salary_min": 15_000_000, "salary_max": 25_000_000, "skills": ["Docker", "AWS Cloud"],
     "seniority_levels": ["JUNIOR", "MID"]},

    # --- Frontend Developer (JavaScript/React) -> DECLINING: 6 previous, 2 recent ---
    {"title": "Frontend Developer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 32,
     "salary_min": 12_000_000, "salary_max": 18_000_000, "skills": ["JavaScript", "React"],
     "seniority_levels": ["MID"]},
    {"title": "React Developer", "company": "MediaVN", "location": "Ha Noi", "days_ago": 36,
     "salary_min": 14_000_000, "salary_max": 20_000_000, "skills": ["React", "JavaScript"],
     "seniority_levels": ["MID"]},
    {"title": "Frontend Engineer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 40,
     "salary_min": 12_000_000, "salary_max": 17_000_000, "skills": ["JavaScript"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "UI Developer Intern", "company": "AdTech", "location": "Da Nang", "days_ago": 44,
     "salary_min": 10_000_000, "salary_max": 15_000_000, "skills": ["React"],
     "seniority_levels": ["INTERN"]},
    {"title": "Frontend Developer", "company": "MediaVN", "location": "Ha Noi", "days_ago": 48,
     "salary_min": 13_000_000, "salary_max": 19_000_000, "skills": ["JavaScript", "React"],
     "seniority_levels": ["MID"]},
    {"title": "Web Developer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 55,
     "salary_min": 11_000_000, "salary_max": 16_000_000, "skills": ["JavaScript"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "Frontend Developer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 5,
     "salary_min": 12_000_000, "salary_max": 18_000_000, "skills": ["React", "JavaScript"],
     "seniority_levels": ["MID"],
     "requirements": "Thanh thao React va JavaScript ES6+, quen lam viec voi REST API.",
     "benefits": "Lam viec linh hoat, ho tro thiet bi, review luong 2 lan/nam."},
    {"title": "React Developer", "company": "AdTech", "location": "Da Nang", "days_ago": 15,
     "salary_min": 11_000_000, "salary_max": 16_000_000, "skills": ["React"],
     "seniority_levels": ["JUNIOR"]},

    # --- Backend Developer (Python/SQL/Docker) -> STABLE: 4 previous, 4 recent ---
    {"title": "Backend Developer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 33,
     "salary_min": 18_000_000, "salary_max": 26_000_000, "skills": ["Python", "SQL"],
     "seniority_levels": ["MID"]},
    {"title": "Backend Engineer", "company": "LogiTech", "location": "Ho Chi Minh City", "days_ago": 38,
     "salary_min": 20_000_000, "salary_max": 28_000_000, "skills": ["Python", "Docker"],
     "seniority_levels": ["MID"]},
    {"title": "Software Engineer Manager", "company": "TechCorp", "location": "Ha Noi", "days_ago": 45,
     "salary_min": 19_000_000, "salary_max": 27_000_000, "skills": ["Python", "SQL", "Docker"],
     "seniority_levels": ["MANAGER"]},
    {"title": "Backend Developer", "company": "AgriData", "location": "Can Tho", "days_ago": 50,
     "salary_min": 14_000_000, "salary_max": 20_000_000, "skills": ["SQL", "Python"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "Backend Developer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 6,
     "salary_min": 19_000_000, "salary_max": 27_000_000, "skills": ["Python", "SQL"],
     "seniority_levels": ["MID"]},
    {"title": "Backend Engineer", "company": "LogiTech", "location": "Ho Chi Minh City", "days_ago": 12,
     "salary_min": 21_000_000, "salary_max": 29_000_000, "skills": ["Python", "Docker"],
     "seniority_levels": ["SENIOR"]},
    {"title": "Software Engineer", "company": "TechCorp", "location": "Ha Noi", "days_ago": 20,
     "salary_min": 20_000_000, "salary_max": 28_000_000, "skills": ["Python", "SQL"],
     "seniority_levels": ["MID"]},
    {"title": "Backend Developer Intern", "company": "AgriData", "location": "Can Tho", "days_ago": 26,
     "salary_min": 15_000_000, "salary_max": 21_000_000, "skills": ["SQL", "Python"],
     "seniority_levels": ["INTERN"]},

    # --- Data Scientist (Python/Machine Learning/SQL) -> RISING: 1 previous, 4 recent ---
    {"title": "Data Analyst", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 40,
     "salary_min": 16_000_000, "salary_max": 22_000_000, "skills": ["SQL", "Python"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "Data Scientist", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 4,
     "salary_min": 25_000_000, "salary_max": 35_000_000, "skills": ["Python", "Machine Learning", "SQL"],
     "seniority_levels": ["SENIOR"]},
    {"title": "Machine Learning Engineer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 9,
     "salary_min": 28_000_000, "salary_max": 40_000_000, "skills": ["Machine Learning", "Python"],
     "seniority_levels": ["SENIOR"],
     "requirements": "Kinh nghiem trien khai mo hinh ML vao production, thanh thao Python.",
     "benefits": "Luong canh tranh, ho tro hoc phi khoa hoc AI/ML, stock option."},
    {"title": "Data Scientist", "company": "TechCorp", "location": "Ha Noi", "days_ago": 16,
     "salary_min": 24_000_000, "salary_max": 33_000_000, "skills": ["Python", "SQL", "Machine Learning"],
     "seniority_levels": ["MID"]},
    {"title": "AI Engineer", "company": "StartupY", "location": "Ha Noi", "days_ago": 24,
     "salary_min": 26_000_000, "salary_max": 36_000_000, "skills": ["Machine Learning", "Python"],
     "seniority_levels": ["MID"]},

    # --- Business Analyst (Excel/SQL/English Communication) -> STABLE: 3 previous, 3 recent ---
    {"title": "Business Analyst", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 34,
     "salary_min": 15_000_000, "salary_max": 20_000_000, "skills": ["Excel", "SQL"],
     "seniority_levels": ["MID"]},
    {"title": "Business Analyst", "company": "AgriData", "location": "Can Tho", "days_ago": 42,
     "salary_min": 12_000_000, "salary_max": 16_000_000, "skills": ["Excel", "English Communication"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "Data Analyst", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 52,
     "salary_min": 14_000_000, "salary_max": 19_000_000, "skills": ["Excel", "SQL", "English Communication"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "Business Analyst", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 8,
     "salary_min": 15_000_000, "salary_max": 21_000_000, "skills": ["Excel", "SQL"],
     "seniority_levels": ["MID"]},
    {"title": "Business Analyst", "company": "AgriData", "location": "Can Tho", "days_ago": 17,
     "salary_min": 12_000_000, "salary_max": 17_000_000, "skills": ["English Communication", "Excel"],
     "seniority_levels": ["JUNIOR"]},
    {"title": "Data Analyst", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 27,
     "salary_min": 14_000_000, "salary_max": 20_000_000, "skills": ["Excel", "SQL", "English Communication"],
     "seniority_levels": ["MID"]},

    # --- Beginner postings: only general/foundational skills, no job-specific
    # technical skill -> job_id resolves to None, career_id still resolves via
    # the CareerSkill fallback (see MarketService._resolve_career_id_fallback). ---
    {"title": "Fresher Chuong Trinh Tap Su CNTT", "company": "TechCorp", "location": "Ha Noi", "days_ago": 5,
     "salary_min": 6_000_000, "salary_max": 9_000_000, "skills": ["Tu duy logic", "Giai quyet van de"],
     "seniority_levels": ["INTERN"],
     "requirements": "Sinh vien nam cuoi/moi tot nghiep nganh CNTT, ham hoc hoi, khong yeu cau kinh nghiem.",
     "benefits": "Duoc dao tao bai ban 3 thang, co hoi len chinh thuc sau chuong trinh."},
    {"title": "Thuc Tap Sinh Cong Nghe", "company": "StartupY", "location": "Ho Chi Minh City", "days_ago": 11,
     "salary_min": 5_000_000, "salary_max": 8_000_000, "skills": ["Toan hoc", "Tu duy logic"],
     "seniority_levels": ["INTERN"]},
]

for _job in SEED_JOB_POSTINGS:
    _job.setdefault("description", f"{_job['title']} at {_job['company']} ({_job['location']}).")
