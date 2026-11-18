"""Comments on a document, optionally anchored to a quote of the text they refer to."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.user import User

QUOTE_MAX_LENGTH = 500
BODY_MAX_LENGTH = 2000


class Comment(Base):
    """A plain-text comment. `quote` and `body` are never HTML: clients must render them as text."""

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    quote: Mapped[str] = mapped_column(String(QUOTE_MAX_LENGTH), default="")
    body: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    author: Mapped["User"] = relationship()
