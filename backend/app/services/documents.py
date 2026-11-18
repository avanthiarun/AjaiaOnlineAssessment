"""Document business logic: sanitizing, create, update, delete and listing."""

import nh3
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import utc_now
from app.models import Document, DocumentShare, User
from app.models.document import DEFAULT_TITLE
from app.permissions import Role

MAX_CONTENT_BYTES = 500 * 1024

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
    doc = Document(owner=owner, title=title or DEFAULT_TITLE, content_html=sanitize_html(content_html))
    db.add(doc)
    db.commit()
    return doc


def update_document(
    db: Session, doc: Document, title: str | None = None, content_html: str | None = None
) -> Document:
    """Apply a partial update; content is sanitized and updated_at always bumped."""
    if title is not None:
        doc.title = title
    if content_html is not None:
        _check_content_size(content_html)
        doc.content_html = sanitize_html(content_html)
    doc.updated_at = utc_now()
    db.commit()
    return doc


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
