"""Request/response models for documents."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.document import TITLE_MAX_LENGTH, Document
from app.permissions import Role
from app.schemas.user import UserOut


def _clean_title(value: str | None) -> str | None:
    """Trim the title and require 1..TITLE_MAX_LENGTH characters."""
    if value is None:
        return None
    value = value.strip()
    if not 1 <= len(value) <= TITLE_MAX_LENGTH:
        raise ValueError(f"Title must be 1 to {TITLE_MAX_LENGTH} characters")
    return value


class DocumentCreate(BaseModel):
    """New document; title defaults to "Untitled document"."""

    title: str | None = None

    _title = field_validator("title")(_clean_title)


class DocumentUpdate(BaseModel):
    """Partial update. Content size (413) is checked in the service, not here (422)."""

    title: str | None = None
    content_html: str | None = None

    _title = field_validator("title")(_clean_title)


class DocumentSummary(BaseModel):
    """List item: metadata plus the caller's role."""

    id: str
    title: str
    owner: UserOut
    role: Role
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Document, role: Role) -> "DocumentSummary":
        """Build from an ORM document and the caller's role."""
        return cls(
            id=doc.id,
            title=doc.title,
            owner=UserOut.model_validate(doc.owner),
            role=role,
            updated_at=doc.updated_at,
        )


class DocumentDetail(DocumentSummary):
    """Full document including its HTML content."""

    content_html: str

    @classmethod
    def from_doc(cls, doc: Document, role: Role) -> "DocumentDetail":
        """Build from an ORM document and the caller's role."""
        summary = DocumentSummary.from_doc(doc, role)
        return cls(**summary.model_dump(), content_html=doc.content_html)


class DocumentListOut(BaseModel):
    """Dashboard lists, each newest first."""

    owned: list[DocumentSummary]
    shared: list[DocumentSummary]
