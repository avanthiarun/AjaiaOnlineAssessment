"""Per-user access grants on a document."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class ShareRole(str, enum.Enum):
    """Access level a shared user has on a document."""

    VIEWER = "viewer"
    EDITOR = "editor"


class DocumentShare(Base):
    """Grants one user viewer or editor access to one document."""

    __tablename__ = "document_shares"
    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_share_document_user"),
        CheckConstraint("role IN ('viewer', 'editor')", name="ck_share_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[ShareRole] = mapped_column(
        Enum(
            ShareRole,
            native_enum=False,
            length=10,
            values_callable=lambda roles: [r.value for r in roles],
            validate_strings=True,
        )
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    document: Mapped["Document"] = relationship(back_populates="shares")
    user: Mapped["User"] = relationship()
