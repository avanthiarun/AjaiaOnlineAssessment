"""Response models for version history."""

from datetime import datetime

from pydantic import BaseModel

from app.models import DocumentVersion


class VersionSummary(BaseModel):
    """One entry in the history list."""

    id: str
    created_at: datetime
    created_by: str  # author's display name

    @classmethod
    def from_version(cls, version: DocumentVersion) -> "VersionSummary":
        """Build from an ORM snapshot (author loaded)."""
        return cls(id=version.id, created_at=version.created_at, created_by=version.created_by.name)


class VersionDetail(VersionSummary):
    """A snapshot with its content, for the read-only preview."""

    title: str
    content_html: str

    @classmethod
    def from_version(cls, version: DocumentVersion) -> "VersionDetail":
        """Build from an ORM snapshot (author loaded)."""
        summary = VersionSummary.from_version(version)
        return cls(**summary.model_dump(), title=version.title, content_html=version.content_html)
