"""Import an uploaded file as a new document."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas.document import DocumentDetail, ImportInfo
from app.services import documents
from app.services.importers import SUPPORTED_EXTENSIONS, UnsupportedFileType, check_extension, file_to_html

CHUNK_SIZE = 64 * 1024

# Both paths have two segments after /api/documents, so they can't be captured by /{doc_id}.
router = APIRouter(prefix="/api/documents/import", tags=["uploads"])


def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, failing with 413 as soon as it exceeds max_bytes."""
    data = bytearray()
    while chunk := file.file.read(CHUNK_SIZE):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"File is larger than {max_bytes // (1024 * 1024)} MB",
            )
    return bytes(data)


@router.get("/info", response_model=ImportInfo)
def import_info(_: User = Depends(get_current_user)) -> ImportInfo:
    """Which file types can be imported, and the size limit (drives the upload UI)."""
    return ImportInfo(extensions=list(SUPPORTED_EXTENSIONS), max_mb=get_settings().max_upload_mb)


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def import_document(
    file: UploadFile, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentDetail:
    """Turn an uploaded file into a new document owned by the uploader."""
    filename = file.filename or ""
    try:
        check_extension(filename)
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc

    data = _read_limited(file, get_settings().max_upload_mb * 1024 * 1024)
    if not data.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty")

    try:
        title, html = file_to_html(filename, data)
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    doc = documents.create_document(db, user, title=title or None, content_html=html)
    return DocumentDetail.from_doc(doc, "owner")
