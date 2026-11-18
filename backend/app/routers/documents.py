"""Document CRUD. Permission checks live in app.permissions, logic in app.services."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from markdownify import markdownify
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
from app.schemas.share import TransferIn
from app.services import documents as service
from app.services import sharing

CONFLICT_MESSAGE = "This document was changed by someone else."

router = APIRouter(prefix="/api/documents", tags=["documents"])


def conflict_response(exc: service.VersionConflict) -> JSONResponse:
    """409 telling the client its copy is stale, with the version it now has to reload."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": CONFLICT_MESSAGE, "current_version": exc.current_version},
    )


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


@router.patch(
    "/{doc_id}",
    response_model=DocumentDetail,
    responses={409: {"description": "Stale base_version; body includes current_version"}},
)
def update_document(
    doc_id: str,
    body: DocumentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentDetail | JSONResponse:
    """Rename and/or save content (used by autosave). 409 if base_version is stale."""
    doc, role = load_doc_for(db, doc_id, user, "edit")
    try:
        doc = service.update_document(
            db, doc, user, title=body.title, content_html=body.content_html, base_version=body.base_version
        )
    except service.VersionConflict as exc:
        return conflict_response(exc)
    return DocumentDetail.from_doc(doc, role)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Delete a document (owner only)."""
    doc, _ = load_doc_for(db, doc_id, user, "delete")
    service.delete_document(db, doc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{doc_id}/transfer", response_model=DocumentDetail)
def transfer_ownership(
    doc_id: str, body: TransferIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentDetail:
    """Owner only: hand the document to someone who has access; the caller becomes an editor."""
    doc, _ = load_doc_for(db, doc_id, user, "transfer")
    sharing.transfer_ownership(db, doc, body.email)
    db.refresh(doc)
    return DocumentDetail.from_doc(doc, "editor")


@router.get("/{doc_id}/export")
def export_document(
    doc_id: str,
    fmt: Literal["md", "html"] = Query("html", alias="format"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download a document the user can view as Markdown or HTML."""
    doc, _ = load_doc_for(db, doc_id, user, "view")
    if fmt == "md":
        body = markdownify(doc.content_html, heading_style="ATX")
    else:
        body = service.standalone_html(doc.title, doc.content_html)
    name = re.sub(r"[^A-Za-z0-9 _-]", "", doc.title).strip() or "document"  # ASCII-safe header
    media = "text/markdown" if fmt == "md" else "text/html"
    headers = {"Content-Disposition": f'attachment; filename="{name}.{fmt}"'}
    return Response(body, media_type=media, headers=headers)
