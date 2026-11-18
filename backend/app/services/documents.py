"""Document business logic: sanitizing, create, update, delete, listing and export."""

import html
from datetime import timedelta

import nh3
from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, joinedload

from app.db import utc_now
from app.models import Document, DocumentShare, DocumentVersion, User
from app.models.document import DEFAULT_TITLE
from app.permissions import Role

MAX_CONTENT_BYTES = 500 * 1024
SNAPSHOT_INTERVAL = timedelta(minutes=5)  # autosave runs every second; history shouldn't
MAX_VERSIONS = 50


class VersionConflict(Exception):
    """The client's base_version is stale: someone else saved content in between."""

    def __init__(self, current_version: int) -> None:
        super().__init__(f"Document is at version {current_version}")
        self.current_version = current_version


# Covers what TipTap's StarterKit + Underline emit. Everything else (scripts, styles,
# event handlers, iframes...) is stripped.
ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "h1", "h2", "h3",
    "ul", "ol", "li", "blockquote", "code", "pre", "hr", "a",
}
ALLOWED_ATTRIBUTES = {"a": {"href"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_html(html: str) -> str:
    """Return HTML reduced to the editor's allowlist."""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )


def standalone_html(title: str, content_html: str) -> str:
    """Wrap (already sanitized) document HTML in a complete page for download."""
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        "</head>\n"
        f"<body>\n{content_html}\n</body>\n"
        "</html>\n"
    )


def _check_content_size(html: str) -> None:
    """Reject content over MAX_CONTENT_BYTES with 413."""
    if len(html.encode()) > MAX_CONTENT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Document content exceeds {MAX_CONTENT_BYTES // 1024} KB",
        )


def create_document(db: Session, owner: User, title: str | None = None, content_html: str = "") -> Document:
    """Create a document owned by `owner` with sanitized content."""
    _check_content_size(content_html)
    doc = Document(
        owner=owner, title=title or DEFAULT_TITLE, content_html=sanitize_html(content_html), updated_by_id=owner.id
    )
    db.add(doc)
    db.commit()
    return doc


def snapshot(db: Session, doc: Document, throttle: bool = True) -> None:
    """Save the document's current content to its history, keeping the newest MAX_VERSIONS.

    With throttle, skip it if the last snapshot is under SNAPSHOT_INTERVAL old. Empty content
    is never saved: there is nothing to go back to.
    """
    if not doc.content_html:
        return
    if throttle:
        latest = db.scalar(
            select(DocumentVersion.created_at)
            .where(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.created_at.desc())
            .limit(1)
        )
        if latest is not None and utc_now() - latest < SNAPSHOT_INTERVAL:
            return
    db.add(
        DocumentVersion(
            document_id=doc.id,
            title=doc.title,
            content_html=doc.content_html,
            created_by_id=doc.updated_by_id or doc.owner_id,  # older docs: assume the owner
        )
    )
    db.flush()
    newest = (
        select(DocumentVersion.id)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.created_at.desc())
        .limit(MAX_VERSIONS)
    )
    db.execute(
        delete(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id, DocumentVersion.id.not_in(newest))
        .execution_options(synchronize_session=False)
    )


def _write_content(db: Session, doc: Document, content_html: str, expected: int, user: User) -> None:
    """Compare-and-set the content and bump `version`; VersionConflict if `expected` is stale."""
    result = db.execute(
        update(Document)
        .where(Document.id == doc.id, Document.version == expected)
        .values(content_html=content_html, version=expected + 1, updated_by_id=user.id)
    )
    if result.rowcount == 0:
        db.rollback()  # also drops the snapshot; expires doc, so .version is re-read
        raise VersionConflict(doc.version)


def update_document(
    db: Session,
    doc: Document,
    user: User,
    title: str | None = None,
    content_html: str | None = None,
    base_version: int | None = None,
) -> Document:
    """Apply a partial update; content is sanitized and updated_at always bumped.

    A content save first snapshots the previous content (throttled), then bumps `version` with
    a compare-and-set UPDATE (atomic, so two simultaneous saves can't both win). With
    base_version, a stale client gets VersionConflict; without it, the save applies on top of
    the latest version (backwards compatible). Titles don't bump it.
    """
    if content_html is not None:
        _check_content_size(content_html)
        snapshot(db, doc)
        expected = doc.version if base_version is None else base_version
        _write_content(db, doc, sanitize_html(content_html), expected, user)
    if title is not None:
        doc.title = title
    doc.updated_at = utc_now()
    db.commit()
    db.refresh(doc)
    return doc


def restore_version(db: Session, doc: Document, version: DocumentVersion, user: User) -> Document:
    """Replace the content with an old version's. The current content is snapshotted first
    (unthrottled), so a restore can itself be undone. The title is left as it is."""
    snapshot(db, doc, throttle=False)
    _write_content(db, doc, version.content_html, doc.version, user)
    doc.updated_at = utc_now()
    db.commit()
    db.refresh(doc)
    return doc


def list_versions(db: Session, doc: Document) -> list[DocumentVersion]:
    """A document's history, newest first, with authors loaded."""
    return list(
        db.scalars(
            select(DocumentVersion)
            .options(joinedload(DocumentVersion.created_by))
            .where(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.created_at.desc())
        )
    )


def get_version(db: Session, doc: Document, version_id: str) -> DocumentVersion:
    """One snapshot of this document (404 if it doesn't exist or belongs to another document)."""
    version = db.get(DocumentVersion, version_id)
    if version is None or version.document_id != doc.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return version


def delete_document(db: Session, doc: Document) -> None:
    """Delete a document; its shares go with it."""
    db.delete(doc)
    db.commit()


def list_for_user(db: Session, user: User) -> tuple[list[Document], list[tuple[Document, Role]]]:
    """Return (owned docs, [(shared doc, role)]), each newest first."""
    owned = db.scalars(
        select(Document)
        .options(joinedload(Document.owner))
        .where(Document.owner_id == user.id)
        .order_by(Document.updated_at.desc())
    ).all()
    shared_rows = db.execute(
        select(Document, DocumentShare.role)
        .join(DocumentShare, DocumentShare.document_id == Document.id)
        .options(joinedload(Document.owner))
        .where(DocumentShare.user_id == user.id)
        .order_by(Document.updated_at.desc())
    ).all()
    return list(owned), [(doc, role.value) for doc, role in shared_rows]
