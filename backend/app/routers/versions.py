"""Version history: list, preview and restore. Permission checks live in app.permissions."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import User
from app.permissions import load_doc_for
from app.routers.documents import conflict_response
from app.schemas.document import DocumentDetail
from app.schemas.version import VersionDetail, VersionSummary
from app.services import documents as service

router = APIRouter(prefix="/api/documents/{doc_id}/versions", tags=["versions"])


@router.get("", response_model=list[VersionSummary])
def list_versions(
    doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[VersionSummary]:
    """Saved versions of a document the caller can view, newest first."""
    doc, _ = load_doc_for(db, doc_id, user, "view")
    return [VersionSummary.from_version(v) for v in service.list_versions(db, doc)]


@router.get("/{version_id}", response_model=VersionDetail)
def get_version(
    doc_id: str, version_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> VersionDetail:
    """One version's content, for a read-only preview."""
    doc, _ = load_doc_for(db, doc_id, user, "view")
    return VersionDetail.from_version(service.get_version(db, doc, version_id))


@router.post("/{version_id}/restore", response_model=DocumentDetail)
def restore_version(
    doc_id: str, version_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentDetail | JSONResponse:
    """Make an old version the current content (the replaced content goes into history)."""
    doc, role = load_doc_for(db, doc_id, user, "edit")
    version = service.get_version(db, doc, version_id)
    try:
        doc = service.restore_version(db, doc, version, user)
    except service.VersionConflict as exc:
        return conflict_response(exc)
    return DocumentDetail.from_doc(doc, role)
