"""Request/response models for document sharing."""

from pydantic import BaseModel, ConfigDict

from app.models import ShareRole
from app.schemas.user import NormalizedEmail, UserOut


class ShareCreate(BaseModel):
    """Share a document with an existing user by email."""

    email: NormalizedEmail
    role: ShareRole


class ShareRoleUpdate(BaseModel):
    """Change an existing share's role."""

    role: ShareRole


class TransferIn(BaseModel):
    """Make another user (who already has access) the owner."""

    email: NormalizedEmail


class ShareOut(BaseModel):
    """One shared user and their role."""

    model_config = ConfigDict(from_attributes=True)

    user: UserOut
    role: ShareRole


class ShareListOut(BaseModel):
    """Everyone with access: the owner plus shared users."""

    owner: UserOut
    shares: list[ShareOut]
