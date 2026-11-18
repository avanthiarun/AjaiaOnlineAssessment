"""Presence business logic: record heartbeats and list who else has a document open."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import utc_now
from app.models import Document, DocumentPresence, DocumentShare, User
from app.schemas.presence import ActiveViewer

ACTIVE_WINDOW = timedelta(seconds=30)


def heartbeat(db: Session, doc: Document, user: User, editing: bool) -> None:
    """Upsert the caller's presence row with last_seen_at = now."""
    values = {"last_seen_at": utc_now(), "is_editing": editing}
    query = select(DocumentPresence).where(
        DocumentPresence.document_id == doc.id, DocumentPresence.user_id == user.id
    )
    row = db.scalar(query)
    if row is None:
        db.add(DocumentPresence(document_id=doc.id, user_id=user.id, **values))
        try:
            db.commit()
            return
        except IntegrityError:  # the same user's other tab inserted first; update that row instead
            db.rollback()
            row = db.scalar(query)
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()


def active_viewers(db: Session, doc: Document, exclude: User) -> list[ActiveViewer]:
    """Users other than `exclude` seen in the last ACTIVE_WINDOW who still have access, by name."""
    rows = db.execute(
        select(User, DocumentPresence.is_editing, DocumentShare.role)
        .join(DocumentPresence, DocumentPresence.user_id == User.id)
        .outerjoin(
            DocumentShare,
            (DocumentShare.document_id == doc.id) & (DocumentShare.user_id == User.id),
        )
        .where(
            DocumentPresence.document_id == doc.id,
            DocumentPresence.user_id != exclude.id,
            DocumentPresence.last_seen_at >= utc_now() - ACTIVE_WINDOW,
        )
        .order_by(User.name)
    ).all()
    viewers = []
    for user, is_editing, share_role in rows:
        role = "owner" if user.id == doc.owner_id else share_role and share_role.value
        if role:  # skip people whose access was revoked since their last heartbeat
            viewers.append(ActiveViewer(id=user.id, name=user.name, role=role, is_editing=is_editing))
    return viewers
