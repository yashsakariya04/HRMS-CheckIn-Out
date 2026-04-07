# app/database.py
"""
Database engine, session factory, and Base model for the HRMS backend.

Base is defined in app/models/__init__.py so it is shared with the partner's
models (which import from app.models). This file re-exports it for backward
compatibility so existing code using `from app.database import Base` still works.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=(settings.APP_ENV == "development"),
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Re-export Base — real definition is in app/models/__init__.py
from app.models import Base  # noqa: E402, F401


def get_db():
    """
    FastAPI dependency — provides one DB session per request.
    Always closed after the request, even on exceptions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()