import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from domains.market.models import Career
from domains.market.repository import MarketRepository
from domains.market.seed_data import SEED_CAREERS, SEED_GENERAL_SKILLS, SEED_SKILLS
from domains.market.service import MarketService


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_market_seed_creates_more_than_100_unique_careers_idempotently(db):
    service = MarketService(db)

    first = service.seed_demo_data()
    first_count = db.query(Career).count()
    second = service.seed_demo_data()
    second_count = db.query(Career).count()

    assert len(SEED_CAREERS) > 100
    assert len({item["title"] for item in SEED_CAREERS}) == len(SEED_CAREERS)
    assert first["careers_seeded"] == len(SEED_CAREERS)
    assert second["careers_seeded"] == len(SEED_CAREERS)
    assert first_count == len(SEED_CAREERS)
    assert second_count == first_count


def test_market_seed_expands_skills_and_renames_legacy_vietnamese_rows(db):
    repo = MarketRepository(db)
    legacy = repo.get_or_create_skill("Toan hoc", "general")
    legacy_id = legacy.id

    result = MarketService(db).seed_demo_data()
    skill_names = {skill.name for skill in repo.list_skills(limit=500)}

    assert result["skills_seeded"] == len(SEED_SKILLS)
    assert len(SEED_SKILLS) >= 80
    assert len(skill_names) == len(SEED_SKILLS)
    assert repo.get_skill(legacy_id).name == "Toán học"
    assert "Toan hoc" not in skill_names
    assert {"Toán học", "Giải quyết vấn đề", "Tư duy logic"} <= skill_names
    assert set(SEED_GENERAL_SKILLS) <= skill_names
