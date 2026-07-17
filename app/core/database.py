from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    # Neon (and most serverless/managed Postgres) can drop idle connections
    # server-side; pre-ping issues a cheap check and reconnects instead of
    # surfacing a stale-connection error on the next real query.
    pool_pre_ping=True,
    echo=False # Set to True for SQL logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
