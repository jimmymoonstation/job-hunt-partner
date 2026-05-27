import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////opt/job-hunt-partner/jobs.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
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


def init_db():
    from src.api import models  # noqa: F401 — registers all models
    Base.metadata.create_all(bind=engine)
    _seed_default_config()


def _seed_default_config():
    with SessionLocal() as db:
        from src.api.models import SearchConfig
        if not db.query(SearchConfig).first():
            db.add(SearchConfig(
                titles_json="[]",
                locations_json="[]",
                levels_json="[]",
                keywords_json="[]",
                excluded_companies_json="[]",
                is_active=True,
            ))
            db.commit()
