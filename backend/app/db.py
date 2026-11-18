"""Database engine, session factory, declarative base and shared column helpers."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Engine, create_engine, event, inspect, text
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetime on both Postgres and SQLite (which drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Re-attach UTC to naive values read back from SQLite."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


def normalize_url(url: str) -> str:
    """Point plain Postgres URLs (as Supabase provides them) at the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def build_engine(url: str) -> Engine:
    """Create an engine with SQLite- or Postgres-appropriate options."""
    url = normalize_url(url)
    if url.startswith("sqlite"):
        sqlite_engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(sqlite_engine, "connect")
        def _enable_foreign_keys(dbapi_conn: Any, _: Any) -> None:
            """SQLite ignores ON DELETE CASCADE unless foreign keys are switched on."""
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return sqlite_engine
    # Small pool: the Supabase free tier caps concurrent connections.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    with SessionLocal() as db:
        yield db


# (table, column, SQL type + constraints) added after the first production deploy.
ADDED_COLUMNS = [("documents", "version", "INTEGER NOT NULL DEFAULT 1")]


def add_missing_columns(target: Engine) -> None:
    """Add columns that create_all() cannot add to tables that already exist.

    A deliberate stand-in for Alembic within the timebox: idempotent, additive only, and the
    ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT syntax works on both SQLite and Postgres.
    """
    inspector = inspect(target)
    for table, column, ddl in ADDED_COLUMNS:
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column not in existing:
            with target.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_db() -> None:
    """Create missing tables, then add any missing columns.

    We skip Alembic on purpose for the 4h timebox; see add_missing_columns.
    """
    import app.models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(engine)
    add_missing_columns(engine)
