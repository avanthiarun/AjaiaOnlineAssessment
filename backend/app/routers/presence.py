"""Presence heartbeats. Permission checks live in app.permissions, logic in app.services."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import User
from app.permissions import load_doc_for
from app.schemas.presence import PresenceIn, PresenceOut
from app.services import presence as service

router = APIRouter(prefix="/api/documents/{doc_id}/presence", tags=["presence"])


@router.post("", response_model=PresenceOut)
def heartbeat(
    doc_id: str, body: PresenceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PresenceOut:
    """Mark the caller as here and return who else is, plus the document's current version."""
    doc, _ = load_doc_for(db, doc_id, user, "view")
    service.heartbeat(db, doc, user, body.editing)
    return PresenceOut(
        viewers=service.active_viewers(db, doc, exclude=user),
        version=doc.version,
        updated_at=doc.updated_at,
    )
