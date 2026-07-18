"""Static sample dataset for demo student profiles, seeded via
GuidanceService.seed_demo_data() (this domain has no seed endpoint of its own yet).

`skills` on each student references skill names by name, reusing the shared
catalog from domains.market.seed_data.SEED_SKILLS rather than defining new
skills here — this domain seeds no Skill rows itself. GuidanceService.seed_demo_data
records each one as a StudentSkillProfile, produced through the real
AI_DRAFT -> VERIFIED evidence chain (see EvidenceService) rather than a direct
insert, so seeded skills are indistinguishable from genuinely-earned ones.
Because of that, market seed data must run before this one (already the case:
GuidanceService.seed_demo_data calls self.market_repo.get_or_create_skill,
which is a lookup-or-create — if market hasn't been seeded yet, these calls
create the skills themselves, just without market's curated `category`).
"""

SEED_STUDENTS = [
    {
        "full_name": "Nguyen Van A",
        "email": "student.demo@career-guidance.local",
        "current_location": "Can Tho",
        "ai_inferred_profile": {
            "interests": ["technology", "problem-solving", "video games"],
            "strengths": ["logical thinking", "math"],
            "notes": "Built up from chat + quiz interactions (see InteractionLog), not a single personality-test result.",
        },
        "skills": ["Tu duy logic", "Toan hoc", "English Communication"],
    },
    {
        "full_name": "Tran Thi B",
        "email": "student.b@career-guidance.local",
        "current_location": "Ho Chi Minh City",
        "ai_inferred_profile": {
            "interests": ["data", "business"],
            "strengths": ["communication", "presentation"],
            "notes": "Leans toward data/business-analyst-style paths.",
        },
        "skills": ["Excel", "SQL", "Giai quyet van de"],
    },
    {
        "full_name": "Le Van C",
        "email": "student.c@career-guidance.local",
        "current_location": "Ha Noi",
        "ai_inferred_profile": {
            "interests": ["programming", "web development"],
            "strengths": ["coding", "logic"],
            "notes": "Leans toward software-development-style paths.",
        },
        "skills": ["Python", "JavaScript", "React"],
    },
]
