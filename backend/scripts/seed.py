"""Seed demo data manually: `python -m scripts.seed` from the backend folder."""

from app.db import SessionLocal, init_db
from app.services.seed import seed_demo_users


def main() -> None:
    """Create tables if needed, then insert the demo users and welcome doc."""
    init_db()
    with SessionLocal() as db:
        seed_demo_users(db)
    print("Seeded demo users (password: demo1234)")


if __name__ == "__main__":
    main()
