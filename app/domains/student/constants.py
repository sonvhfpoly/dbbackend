from enum import StrEnum


class StudentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class EducationLevel(StrEnum):
    HIGH_SCHOOL = "high_school"
    VOCATIONAL = "vocational"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    BOOTCAMP = "bootcamp"
    OTHER = "other"


class SkillEventType(StrEnum):
    TASK_EVIDENCE = "task_evidence"
    MENTOR_FEEDBACK = "mentor_feedback"
    SELF_ASSESSMENT = "self_assessment"
    ASSESSMENT = "assessment"
    PORTFOLIO = "portfolio"


class SourceService(StrEnum):
    TASK_SERVICE = "task_service"
    STUDENT_SERVICE = "student_service"
    IMPORT = "import"
    MANUAL = "manual"


class RecommendationGenerator(StrEnum):
    RULE_BASED_V1 = "rule_based_v1"
    LLM_V1 = "llm_v1"
    SEED_RULE_BASED_V1 = "seed_rule_based_v1"


class RecommendationStatus(StrEnum):
    DRAFT = "draft"
    READY_FOR_DEMO = "ready_for_demo"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"
