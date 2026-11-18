"""Sharing business logic: list, add/update (upsert) and revoke document shares."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Document, DocumentShare, ShareRole, User


def list_shares(db: Session, doc: Document) -> list[DocumentShare]:
    """All shares on a document, oldest first, with users loaded."""
    query = (
        select(DocumentShare)
        .options(joinedload(DocumentShare.user))
        .where(DocumentShare.document_id == doc.id)
        .order_by(DocumentShare.created_at)
    )
    return list(db.scalars(query))


def _get_share(db: Session, doc: Document, user_id: str) -> DocumentShare | None:
    """The share for (doc, user), if any."""
    return db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == doc.id, DocumentShare.user_id == user_id
        )
    )


def upsert_share(db: Session, doc: Document, email: str, role: ShareRole) -> tuple[DocumentShare, bool]:
    """Share with the user at `email`, or update their role. Returns (share, created)."""
    target = db.scalar(select(User).where(User.email == email))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")
    if target.id == doc.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot share a document with its owner")

    share = _get_share(db, doc, target.id)
    created = share is None
    if share is None:
        share = DocumentShare(document=doc, user=target, role=role)
        db.add(share)
    else:
        share.role = role
    db.commit()
    return share, created


def set_role(db: Session, doc: Document, user_id: str, role: ShareRole) -> DocumentShare:
    """Change the role of an existing share (404 if there is none)."""
    share = _get_share(db, doc, user_id)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    share.role = role
    db.commit()
    return share


def transfer_ownership(db: Session, doc: Document, email: str) -> None:
    """Make the user at `email` the owner; the old owner stays on as an editor.

    The new owner must already have access. Their share row is removed (owners don't have
    one) and the old owner gets an editor share, all committed together.
    """
    target = db.scalar(select(User).where(User.email == email))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")
    if target.id == doc.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You already own this document")
    share = _get_share(db, doc, target.id)
    if share is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Share the document with them before making them the owner")

    old_owner_id = doc.owner_id
    db.delete(share)
    db.flush()  # free the (document, user) slot before the old owner's share is inserted
    doc.owner_id = target.id
    db.add(DocumentShare(document_id=doc.id, user_id=old_owner_id, role=ShareRole.EDITOR))
    db.commit()


def revoke(db: Session, doc: Document, user_id: str) -> None:
    """Remove a user's access (404 if they had none)."""
    share = _get_share(db, doc, user_id)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    db.delete(share)
    db.commit()
