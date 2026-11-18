"""Who has a document open right now (one row per user per document, refreshed by heartbeats)."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utc_now


class DocumentPresence(Base):
    """The last heartbeat a user sent for a document, and whether they were typing."""

    __tablename__ = "document_presence"
    __table_args__ = (UniqueConstraint("document_id", "user_id", name="uq_presence_document_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    is_editing: Mapped[bool] = mapped_column(default=False)
