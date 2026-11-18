"""Documents: rich text stored as sanitized HTML."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.share import DocumentShare
    from app.models.user import User

TITLE_MAX_LENGTH = 200
DEFAULT_TITLE = "Untitled document"


class Document(Base):
    """A document with exactly one owner and any number of shares."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), default=DEFAULT_TITLE)
    content_html: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, onupdate=utc_now)

    owner: Mapped["User"] = relationship()
    shares: Mapped[list["DocumentShare"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
