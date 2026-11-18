"""Snapshots of a document's earlier content, for version history and restore."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.user import User


class DocumentVersion(Base):
    """The document as it was at `created_at`, last edited by `created_by`."""

    __tablename__ = "document_versions"
    __table_args__ = (Index("ix_document_versions_document_created", "document_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    content_html: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))

    created_by: Mapped["User"] = relationship()
