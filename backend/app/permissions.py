"""The single place that decides who can view, edit, share or delete a document."""

from collections.abc import Callable
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentShare, User

Role = Literal["owner", "editor", "viewer"]
Need = Literal["view", "edit", "share", "delete"]


def get_role(db: Session, doc: Document, user: User) -> Role | None:
    """Return the user's role on the document, or None if they have no access."""
    if doc.owner_id == user.id:
        return "owner"
    share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == doc.id, DocumentShare.user_id == user.id
        )
    )
    return share.role.value if share else None  # type: ignore[return-value]


def can_view(role: Role | None) -> bool:
    """Anyone with a role can view."""
    return role is not None


def can_edit(role: Role | None) -> bool:
    """Owners and editors can edit."""
    return role in ("owner", "editor")


def can_share(role: Role | None) -> bool:
    """Only the owner can manage sharing."""
    return role == "owner"


def can_delete(role: Role | None) -> bool:
    """Only the owner can delete."""
    return role == "owner"


_CHECKS: dict[Need, Callable[[Role | None], bool]] = {
    "view": can_view,
    "edit": can_edit,
    "share": can_share,
    "delete": can_delete,
}


def load_doc_for(db: Session, doc_id: str, user: User, need: Need) -> tuple[Document, Role]:
    """Load a document the user is allowed to act on, returning it with their role.

    404 if the doc does not exist or the user has no access (so IDs do not leak);
    403 if they can see it but lack the needed permission.
    """
    doc = db.get(Document, doc_id)
    role = get_role(db, doc, user) if doc else None
    if doc is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if not _CHECKS[need](role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You do not have permission to {need} this document")
    return doc, role
