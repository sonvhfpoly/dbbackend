"""Static sample dataset for the /market/seed-demo-data endpoint.

Job posting `days_ago` values are deliberately chosen so that, once ingested,
`MarketService.update_market_trends` (30-day growth window) produces a mix of
RISING / STABLE / DECLINING careers, and so that some skills are visibly
concentrated in a few locations only (a shortage signal for the rest).
"""

SEED_SKILLS = [
    {"name": "Python", "category": "Programming"},
    {"name": "JavaScript", "category": "Programming"},
    {"name": "React", "category": "Programming"},
    {"name": "SQL", "category": "Data"},
    {"name": "Docker", "category": "DevOps"},
    {"name": "Kubernetes", "category": "DevOps"},
    {"name": "AWS Cloud", "category": "DevOps"},
    {"name": "Machine Learning", "category": "Data"},
    {"name": "Excel", "category": "Office"},
    {"name": "English Communication", "category": "Soft Skill"},
]

SEED_CAREERS = [
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
     "salary_min": 20_000_000, "salary_max": 30_000_000, "skills": ["Docker", "AWS Cloud"]},
    {"title": "SRE Engineer", "company": "TechCorp", "location": "Ha Noi", "days_ago": 35,
     "salary_min": 25_000_000, "salary_max": 35_000_000, "skills": ["Kubernetes", "Docker"]},
    {"title": "DevOps Engineer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 3,
     "salary_min": 22_000_000, "salary_max": 32_000_000, "skills": ["Docker", "Kubernetes", "AWS Cloud"]},
    {"title": "Cloud Engineer", "company": "CloudViet", "location": "Ho Chi Minh City", "days_ago": 7,
     "salary_min": 20_000_000, "salary_max": 28_000_000, "skills": ["AWS Cloud", "Docker"]},
    {"title": "Site Reliability Engineer", "company": "TechCorp", "location": "Ha Noi", "days_ago": 10,
     "salary_min": 25_000_000, "salary_max": 38_000_000, "skills": ["Kubernetes", "Docker"]},
    {"title": "DevOps Engineer", "company": "StartupY", "location": "Ha Noi", "days_ago": 14,
     "salary_min": 18_000_000, "salary_max": 26_000_000, "skills": ["Docker", "AWS Cloud"]},
    {"title": "Platform Engineer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 18,
     "salary_min": 24_000_000, "salary_max": 34_000_000, "skills": ["Kubernetes", "AWS Cloud"]},
    {"title": "DevOps Engineer", "company": "LogiTech", "location": "Ho Chi Minh City", "days_ago": 22,
     "salary_min": 20_000_000, "salary_max": 30_000_000, "skills": ["Docker", "Kubernetes"]},

    # --- Frontend Developer (JavaScript/React) -> DECLINING: 6 previous, 2 recent ---
    {"title": "Frontend Developer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 32,
     "salary_min": 12_000_000, "salary_max": 18_000_000, "skills": ["JavaScript", "React"]},
    {"title": "React Developer", "company": "MediaVN", "location": "Ha Noi", "days_ago": 36,
     "salary_min": 14_000_000, "salary_max": 20_000_000, "skills": ["React", "JavaScript"]},
    {"title": "Frontend Engineer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 40,
     "salary_min": 12_000_000, "salary_max": 17_000_000, "skills": ["JavaScript"]},
    {"title": "UI Developer", "company": "AdTech", "location": "Da Nang", "days_ago": 44,
     "salary_min": 10_000_000, "salary_max": 15_000_000, "skills": ["React"]},
    {"title": "Frontend Developer", "company": "MediaVN", "location": "Ha Noi", "days_ago": 48,
     "salary_min": 13_000_000, "salary_max": 19_000_000, "skills": ["JavaScript", "React"]},
    {"title": "Web Developer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 55,
     "salary_min": 11_000_000, "salary_max": 16_000_000, "skills": ["JavaScript"]},
    {"title": "Frontend Developer", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 5,
     "salary_min": 12_000_000, "salary_max": 18_000_000, "skills": ["React", "JavaScript"]},
    {"title": "React Developer", "company": "AdTech", "location": "Da Nang", "days_ago": 15,
     "salary_min": 11_000_000, "salary_max": 16_000_000, "skills": ["React"]},

    # --- Backend Developer (Python/SQL/Docker) -> STABLE: 4 previous, 4 recent ---
    {"title": "Backend Developer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 33,
     "salary_min": 18_000_000, "salary_max": 26_000_000, "skills": ["Python", "SQL"]},
    {"title": "Backend Engineer", "company": "LogiTech", "location": "Ho Chi Minh City", "days_ago": 38,
     "salary_min": 20_000_000, "salary_max": 28_000_000, "skills": ["Python", "Docker"]},
    {"title": "Software Engineer", "company": "TechCorp", "location": "Ha Noi", "days_ago": 45,
     "salary_min": 19_000_000, "salary_max": 27_000_000, "skills": ["Python", "SQL", "Docker"]},
    {"title": "Backend Developer", "company": "AgriData", "location": "Can Tho", "days_ago": 50,
     "salary_min": 14_000_000, "salary_max": 20_000_000, "skills": ["SQL", "Python"]},
    {"title": "Backend Developer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 6,
     "salary_min": 19_000_000, "salary_max": 27_000_000, "skills": ["Python", "SQL"]},
    {"title": "Backend Engineer", "company": "LogiTech", "location": "Ho Chi Minh City", "days_ago": 12,
     "salary_min": 21_000_000, "salary_max": 29_000_000, "skills": ["Python", "Docker"]},
    {"title": "Software Engineer", "company": "TechCorp", "location": "Ha Noi", "days_ago": 20,
     "salary_min": 20_000_000, "salary_max": 28_000_000, "skills": ["Python", "SQL"]},
    {"title": "Backend Developer", "company": "AgriData", "location": "Can Tho", "days_ago": 26,
     "salary_min": 15_000_000, "salary_max": 21_000_000, "skills": ["SQL", "Python"]},

    # --- Data Scientist (Python/Machine Learning/SQL) -> RISING: 1 previous, 4 recent ---
    {"title": "Data Analyst", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 40,
     "salary_min": 16_000_000, "salary_max": 22_000_000, "skills": ["SQL", "Python"]},
    {"title": "Data Scientist", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 4,
     "salary_min": 25_000_000, "salary_max": 35_000_000, "skills": ["Python", "Machine Learning", "SQL"]},
    {"title": "Machine Learning Engineer", "company": "FinTechX", "location": "Ho Chi Minh City", "days_ago": 9,
     "salary_min": 28_000_000, "salary_max": 40_000_000, "skills": ["Machine Learning", "Python"]},
    {"title": "Data Scientist", "company": "TechCorp", "location": "Ha Noi", "days_ago": 16,
     "salary_min": 24_000_000, "salary_max": 33_000_000, "skills": ["Python", "SQL", "Machine Learning"]},
    {"title": "AI Engineer", "company": "StartupY", "location": "Ha Noi", "days_ago": 24,
     "salary_min": 26_000_000, "salary_max": 36_000_000, "skills": ["Machine Learning", "Python"]},

    # --- Business Analyst (Excel/SQL/English Communication) -> STABLE: 3 previous, 3 recent ---
    {"title": "Business Analyst", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 34,
     "salary_min": 15_000_000, "salary_max": 20_000_000, "skills": ["Excel", "SQL"]},
    {"title": "Business Analyst", "company": "AgriData", "location": "Can Tho", "days_ago": 42,
     "salary_min": 12_000_000, "salary_max": 16_000_000, "skills": ["Excel", "English Communication"]},
    {"title": "Data Analyst", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 52,
     "salary_min": 14_000_000, "salary_max": 19_000_000, "skills": ["Excel", "SQL", "English Communication"]},
    {"title": "Business Analyst", "company": "RetailPro", "location": "Ho Chi Minh City", "days_ago": 8,
     "salary_min": 15_000_000, "salary_max": 21_000_000, "skills": ["Excel", "SQL"]},
    {"title": "Business Analyst", "company": "AgriData", "location": "Can Tho", "days_ago": 17,
     "salary_min": 12_000_000, "salary_max": 17_000_000, "skills": ["English Communication", "Excel"]},
    {"title": "Data Analyst", "company": "ShopEase", "location": "Ho Chi Minh City", "days_ago": 27,
     "salary_min": 14_000_000, "salary_max": 20_000_000, "skills": ["Excel", "SQL", "English Communication"]},
]

for _job in SEED_JOB_POSTINGS:
    _job.setdefault("description", f"{_job['title']} at {_job['company']} ({_job['location']}).")
