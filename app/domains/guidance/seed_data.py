"""Static sample dataset for the /guidance/seed-demo-data endpoint.

A deliberate mix of PathType and location (including remote/nationwide,
location=None) so DiversityValidator and RegionExpansionValidator have real
material to act on instead of a single-track catalog. The demo student's
current_location is a smaller city (not one of the two covered by every path)
so the region-expansion case actually has a chance to trigger.
"""

SEED_EDUCATION_PATHS = [
    {
        "name": "Dai hoc Bach Khoa - Ky su Phan mem",
        "type": "UNIVERSITY",
        "duration": "4 nam",
        "requirements": "Tot nghiep THPT, thi dau ky thi tuyen sinh dai hoc",
        "location": "Ho Chi Minh City",
    },
    {
        "name": "Cao dang FPT Polytechnic - CNTT ung dung",
        "type": "VOCATIONAL",
        "duration": "2 nam",
        "requirements": "Tot nghiep THPT hoac THCS",
        "location": "Ho Chi Minh City",
    },
    {
        "name": "Dai hoc Kinh te - Quan tri Kinh doanh",
        "type": "UNIVERSITY",
        "duration": "4 nam",
        "requirements": "Tot nghiep THPT, thi dau ky thi tuyen sinh dai hoc",
        "location": "Ha Noi",
    },
    {
        "name": "Trung tam dao tao nghe DevOps & Cloud",
        "type": "VOCATIONAL",
        "duration": "1 nam",
        "requirements": "Bien co ban ve lap trinh",
        "location": None,
    },
    {
        "name": "Data Science Bootcamp (truc tuyen)",
        "type": "SHORT_COURSE",
        "duration": "6 thang",
        "requirements": "Bien Python co ban",
        "location": None,
    },
    {
        "name": "Khoa hoc truc tuyen Business Analyst",
        "type": "SHORT_COURSE",
        "duration": "3 thang",
        "requirements": "Khong yeu cau nen tang truoc",
        "location": None,
    },
]

SEED_STUDENT = {
    "full_name": "Nguyen Van A",
    "email": "student.demo@career-guidance.local",
    "current_location": "Can Tho",
    "ai_inferred_profile": {
        "interests": ["technology", "problem-solving", "video games"],
        "strengths": ["logical thinking", "math"],
        "notes": "Built up from chat + quiz interactions (see InteractionLog), not a single personality-test result.",
    },
}
