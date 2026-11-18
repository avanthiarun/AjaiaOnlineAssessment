"""Document CRUD. Permission checks live in app.permissions, logic in app.services."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import User
from app.permissions import load_doc_for
from app.schemas.document import (
    DocumentCreate,
    DocumentDetail,
    DocumentListOut,
    DocumentSummary,
    DocumentUpdate,
)
from app.services import documents as service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=DocumentListOut)
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DocumentListOut:
    """Documents the user owns and documents shared with them."""
    owned, shared = service.list_for_user(db, user)
    return DocumentListOut(
        owned=[DocumentSummary.from_doc(doc, "owner") for doc in owned],
        shared=[DocumentSummary.from_doc(doc, role) for doc, role in shared],
    )


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def create_document(
    body: DocumentCreate | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentDetail:
    """Create a new (optionally titled) empty document."""
    doc = service.create_document(db, user, title=body.title if body else None)
    return DocumentDetail.from_doc(doc, "owner")


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(
    doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentDetail:
    """Open a document the user can view."""
    doc, role = load_doc_for(db, doc_id, user, "view")
    return DocumentDetail.from_doc(doc, role)


@router.patch("/{doc_id}", response_model=DocumentDetail)
def update_document(
    doc_id: str,
    body: DocumentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentDetail:
    """Rename and/or save content (used by autosave)."""
    doc, role = load_doc_for(db, doc_id, user, "edit")
    doc = service.update_document(db, doc, title=body.title, content_html=body.content_html)
    return DocumentDetail.from_doc(doc, role)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Delete a document (owner only)."""
    doc, _ = load_doc_for(db, doc_id, user, "delete")
    service.delete_document(db, doc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
