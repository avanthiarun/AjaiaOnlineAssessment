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
ADDED_COLUMNS = [
    ("documents", "version", "INTEGER NOT NULL DEFAULT 1"),
    ("documents", "updated_by_id", "VARCHAR(36) REFERENCES users(id)"),
]


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


def update_share_role_check(target: Engine) -> None:
    """Make an existing Postgres ck_share_role allow every current ShareRole (e.g. "commenter").

    create_all() never alters constraints on existing tables. On Postgres we read the current
    definition and, only if a role is missing, drop and re-add it in one transaction. SQLite
    is skipped: it can't alter constraints, and its databases (tests, local dev) are recreated.
    """
    from app.models.share import SHARE_ROLE_CHECK, SHARE_ROLE_CHECK_NAME, ShareRole

    if target.dialect.name != "postgresql":
        return
    with target.begin() as conn:
        current = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = :name AND conrelid = 'document_shares'::regclass"
            ),
            {"name": SHARE_ROLE_CHECK_NAME},
        ).scalar()
        if current is not None and all(f"'{role.value}'" in current for role in ShareRole):
            return
        conn.execute(text(f"ALTER TABLE document_shares DROP CONSTRAINT IF EXISTS {SHARE_ROLE_CHECK_NAME}"))
        conn.execute(
            text(f"ALTER TABLE document_shares ADD CONSTRAINT {SHARE_ROLE_CHECK_NAME} CHECK ({SHARE_ROLE_CHECK})")
        )


def run_migrations(target: Engine) -> None:
    """The small, idempotent schema changes create_all() can't make (our stand-in for Alembic):

    1. add_missing_columns: new columns on existing tables (SQLite and Postgres).
    2. update_share_role_check: widen the share-role CHECK constraint (Postgres only).
    Every step checks the current schema first, so this is safe to run on every startup.
    """
    add_missing_columns(target)
    update_share_role_check(target)


def init_db() -> None:
    """Create missing tables, then apply run_migrations.

    We skip Alembic on purpose for the 4h timebox; see run_migrations.
    """
    import app.models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(engine)
    run_migrations(engine)
