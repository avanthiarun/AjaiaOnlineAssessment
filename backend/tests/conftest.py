"""Test setup: an isolated SQLite database, never the real (Supabase) DATABASE_URL."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

# Must run before any `app` import: the engine and settings are built at import time,
# and real env vars take precedence over backend/.env.
_TEST_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ.update(
    ENV="development",
    DATABASE_URL=f"sqlite:///{_TEST_DB.as_posix()}",
    SESSION_SECRET="test-session-secret",
    SEED_ON_START="false",
    MAX_UPLOAD_MB="5",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401  (registers tables)
from app.auth.passwords import hash_password  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from tests.helpers import PASSWORD, login  # noqa: E402

_PASSWORD_HASH = hash_password(PASSWORD)  # hash once; bcrypt is slow on purpose


@pytest.fixture(autouse=True)
def fresh_db() -> Iterator[None]:
    """Give every test empty tables."""
    assert engine.dialect.name == "sqlite", "tests must never run against Supabase"
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def users() -> dict[str, User]:
    """Seed alice, bob and carol."""
    with SessionLocal() as db:
        created = {
            name: User(email=f"{name}@ajaia.test", name=name.title(), password_hash=_PASSWORD_HASH)
            for name in ("alice", "bob", "carol")
        }
        db.add_all(created.values())
        db.commit()
        return created


@pytest.fixture
def anon() -> TestClient:
    """A client with no session."""
    return TestClient(app)


@pytest.fixture
def alice(users: dict[str, User]) -> TestClient:
    """Signed-in client for alice (her own cookie jar)."""
    return login(TestClient(app), "alice@ajaia.test")


@pytest.fixture
def bob(users: dict[str, User]) -> TestClient:
    """Signed-in client for bob."""
    return login(TestClient(app), "bob@ajaia.test")


@pytest.fixture
def carol(users: dict[str, User]) -> TestClient:
    """Signed-in client for carol."""
    return login(TestClient(app), "carol@ajaia.test")
