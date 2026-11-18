"""Request/response models for users and login."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _normalize_email(value: str) -> str:
    """Trim and lowercase (matching how emails are stored); reject blank values."""
    value = value.strip().lower()
    if not value:
        raise ValueError("Email is required")
    return value


NormalizedEmail = Annotated[str, Field(min_length=1, max_length=320), AfterValidator(_normalize_email)]


class LoginIn(BaseModel):
    """Login form."""

    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    """Public view of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str


class DemoUserOut(BaseModel):
    """Demo account shown on the login page (no id exposed)."""

    model_config = ConfigDict(from_attributes=True)

    email: str
    name: str
