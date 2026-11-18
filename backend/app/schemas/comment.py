"""Request/response models for comments. Bodies and quotes are plain text, never HTML."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.comment import BODY_MAX_LENGTH, QUOTE_MAX_LENGTH
from app.schemas.user import UserOut


class CommentCreate(BaseModel):
    """A new comment; `quote` is the selected text it refers to (optional)."""

    quote: str = Field("", max_length=QUOTE_MAX_LENGTH)
    body: str

    @field_validator("quote")
    @classmethod
    def _trim_quote(cls, value: str) -> str:
        return value.strip()

    @field_validator("body")
    @classmethod
    def _check_body(cls, value: str) -> str:
        """Trim and require 1..BODY_MAX_LENGTH characters."""
        value = value.strip()
        if not 1 <= len(value) <= BODY_MAX_LENGTH:
            raise ValueError(f"Comment must be 1 to {BODY_MAX_LENGTH} characters")
        return value


class CommentUpdate(BaseModel):
    """Resolve or reopen a comment."""

    resolved: bool


class CommentOut(BaseModel):
    """A comment plus what the caller may do with it, so the UI needn't repeat the rules."""

    id: str
    author: UserOut
    quote: str
    body: str
    resolved: bool
    created_at: datetime
    can_resolve: bool
    can_delete: bool
