"""Request/response models for presence heartbeats."""

from datetime import datetime

from pydantic import BaseModel

from app.permissions import Role


class PresenceIn(BaseModel):
    """A heartbeat: the caller has the document open, and whether they are typing."""

    editing: bool = False


class ActiveViewer(BaseModel):
    """Another user who has the document open."""

    id: str
    name: str
    role: Role
    is_editing: bool


class PresenceOut(BaseModel):
    """Who else is here, plus the document's current version so stale tabs can offer a reload."""

    viewers: list[ActiveViewer]
    version: int
    updated_at: datetime
