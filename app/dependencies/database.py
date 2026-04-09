"""
app/dependencies/database.py — Async Database Session
======================================================
Sets up the SQLAlchemy async database engine and provides a FastAPI
dependency that yields a database session for each request.

Non-technical summary:
----------------------
Every time the app needs to read or write data (employees, attendance,
leaves, etc.), it needs a "connection" to the database. This file
creates that connection system.

  - `engine`            : The low-level database connection pool.
  - `AsyncSessionLocal` : A factory that creates individual sessions
                          (think of a session as a single conversation
                          with the database).
  - `get_db`            : A FastAPI dependency — automatically opens a
                          session at the start of a request and closes
                          it when the request finishes.

Usage in a router:
    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        result = await db.execute(...)
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
# The engine manages the underlying connection pool to PostgreSQL.
# echo=True logs every SQL query to the console — useful for debugging,
# but should be set to False in production to reduce noise.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
)

# ── Session factory ───────────────────────────────────────────────────────────
# AsyncSessionLocal() creates a new async database session.
# expire_on_commit=False means ORM objects remain usable after a commit
# (important for async code where lazy loading is not available).
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Opens a new AsyncSession, yields it to the route handler, then
    automatically closes it when the request is done — even if an
    exception occurs.

    Usage:
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
