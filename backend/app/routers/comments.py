"""Comment endpoints. Permission checks live in app.permissions, logic in app.services."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import User
from app.permissions import load_doc_for
from app.schemas.comment import CommentCreate, CommentOut, CommentUpdate
from app.services import comments as service

router = APIRouter(prefix="/api/documents/{doc_id}/comments", tags=["comments"])


@router.get("", response_model=list[CommentOut])
def list_comments(
    doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CommentOut]:
    """Every comment (open and resolved) on a document the caller can view."""
    doc, role = load_doc_for(db, doc_id, user, "view")
    return [service.to_out(c, user, role) for c in service.list_comments(db, doc)]


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    doc_id: str, body: CommentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CommentOut:
    """Comment on the document (owners, editors and commenters)."""
    doc, role = load_doc_for(db, doc_id, user, "comment")
    return service.to_out(service.create_comment(db, doc, user, body.quote, body.body), user, role)


@router.patch("/{comment_id}", response_model=CommentOut)
def update_comment(
    doc_id: str,
    comment_id: str,
    body: CommentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    """Resolve or reopen (editors, the owner, or the comment's author)."""
    doc, role = load_doc_for(db, doc_id, user, "view")
    comment = service.get_for_action(db, doc, comment_id, user, role, "resolve")
    return service.to_out(service.set_resolved(db, comment, body.resolved), user, role)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    doc_id: str, comment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Delete (the comment's author or the document's owner)."""
    doc, role = load_doc_for(db, doc_id, user, "view")
    service.delete_comment(db, service.get_for_action(db, doc, comment_id, user, role, "delete"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
