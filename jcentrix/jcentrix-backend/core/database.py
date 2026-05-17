# ─────────────────────────────────────────────────────────
# core/database.py — Database Engine + Session Factory
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Sets up the SQLAlchemy async engine that connects to
#   PostgreSQL, creates a session factory for making queries,
#   and defines the Base class that all ORM models inherit from.
#
# FLOW:
#   1. Engine is created with your DATABASE_URL
#   2. AsyncSession factory is created from the engine
#   3. All models inherit from Base → SQLAlchemy knows about them
#   4. get_db() is a FastAPI dependency that provides a session
#      per request and closes it automatically when done.
# ─────────────────────────────────────────────────────────

# create_async_engine: Creates an async database connection pool.
# Async means: while waiting for DB, FastAPI can handle other requests.
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# sessionmaker: A factory that creates new database session objects.
from sqlalchemy.orm import sessionmaker

# DeclarativeBase: Base class for all ORM models. Every model (User, Job, etc.)
# will inherit from this to be recognized by SQLAlchemy.
from sqlalchemy.orm import DeclarativeBase

# AsyncGenerator: Type hint for the async generator function below
from typing import AsyncGenerator

# Import our settings object to get the DATABASE_URL
from core.config import settings


# ── Step 1: Create the Async Engine ──────────────────────
# The engine manages the connection pool to PostgreSQL.
# echo=True: prints every SQL query to the console (great for debugging).
#            Set to False in production.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True if settings.ENVIRONMENT == "development" else False,
)


# ── Step 2: Create the Session Factory ───────────────────
# AsyncSessionLocal is a class that creates new session objects.
# Each request gets its own session (see get_db below).
# expire_on_commit=False: After committing, objects stay usable
#                         (important for async workflows).
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Step 3: Create the Declarative Base ──────────────────
# All ORM model classes will inherit from Base.
# SQLAlchemy uses this to track which tables exist.
class Base(DeclarativeBase):
    pass


# ── Step 4: Database Dependency for FastAPI ───────────────
# This is an async generator function used as a FastAPI dependency.
# HOW IT WORKS:
#   - FastAPI calls get_db() before each request
#   - It creates a new session (AsyncSessionLocal())
#   - It yields the session to the route handler via `yield`
#   - After the request finishes (or errors), the finally block
#     closes the session automatically — no memory leaks.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.
    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session          # Give session to the route handler
            await session.commit() # Auto-commit if no errors occurred
        except Exception:
            await session.rollback()  # Undo changes if something went wrong
            raise                     # Re-raise the exception
        # Session is automatically closed when `async with` block ends


# ── Step 5: Helper to Create All Tables ──────────────────
# This function creates all tables defined in our models.
# Called once at app startup in main.py.
# NOTE: In production, use Alembic migrations instead of this.
async def create_all_tables():
    """Creates all database tables based on the ORM models."""
    async with engine.begin() as conn:
        # run_sync: Runs synchronous SQLAlchemy operations in async context
        await conn.run_sync(Base.metadata.create_all)
