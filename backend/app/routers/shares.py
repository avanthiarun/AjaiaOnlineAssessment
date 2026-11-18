"""Document sharing endpoints. Permission checks live in app.permissions."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import User
from app.permissions import load_doc_for
from app.schemas.share import ShareCreate, ShareListOut, ShareOut, ShareRoleUpdate
from app.schemas.user import UserOut
from app.services import sharing as service

router = APIRouter(prefix="/api/documents/{doc_id}/shares", tags=["shares"])


@router.get("", response_model=ShareListOut)
def list_shares(
    doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareListOut:
    """Owner and shared users of a document the caller can view."""
    doc, _ = load_doc_for(db, doc_id, user, "view")
    return ShareListOut(
        owner=UserOut.model_validate(doc.owner),
        shares=[ShareOut.model_validate(s) for s in service.list_shares(db, doc)],
    )


@router.post("", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
def add_share(
    doc_id: str,
    body: ShareCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareOut:
    """Share with a user by email; 201 if new, 200 if their role was updated."""
    doc, _ = load_doc_for(db, doc_id, user, "share")
    share, created = service.upsert_share(db, doc, body.email, body.role)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ShareOut.model_validate(share)


# Registered before /{user_id} so "me" is not treated as a user id.
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def leave_document(
    doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Let a shared user remove their own access."""
    doc, role = load_doc_for(db, doc_id, user, "view")
    if role == "owner":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Owners cannot leave their own document")
    service.revoke(db, doc, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{user_id}", response_model=ShareOut)
def change_role(
    doc_id: str,
    user_id: str,
    body: ShareRoleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareOut:
    """Change a shared user's role (owner only)."""
    doc, _ = load_doc_for(db, doc_id, user, "share")
    return ShareOut.model_validate(service.set_role(db, doc, user_id, body.role))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    doc_id: str, user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Revoke a user's access (owner only)."""
    doc, _ = load_doc_for(db, doc_id, user, "share")
    service.revoke(db, doc, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
