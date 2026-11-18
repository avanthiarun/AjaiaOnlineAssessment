"""User accounts."""

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db import Base, UTCDateTime, utc_now


class User(Base):
    """A person who can own and be shared documents."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    @validates("email")
    def _normalize_email(self, _: str, value: str) -> str:
        """Store emails trimmed and lowercased so lookups are case-insensitive."""
        return value.strip().lower()
