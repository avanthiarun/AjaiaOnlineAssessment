"""The single place that decides who can view, comment, edit, share, delete or transfer a document.

    action     owner  editor  commenter  viewer  (no access)
    view       yes    yes     yes        yes     404
    comment    yes    yes     yes        no      404
    edit       yes    yes     no         no      404
    share      yes    no      no         no      404
    delete     yes    no      no         no      404
    transfer   yes    no      no         no      404

On an existing comment (the caller must also be able to view the document):

    action     owner  editor  commenter  viewer
    resolve    yes    yes     author     author
    delete     yes    author  author     author

"author" means only on their own comments. "no" is a 403. Users without access get 404 for
everything, so document IDs don't leak. tests/test_permissions.py checks every cell of both tables.
"""

from collections.abc import Callable
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentShare, User

Role = Literal["owner", "editor", "commenter", "viewer"]
Need = Literal["view", "comment", "edit", "share", "delete", "transfer"]
CommentAction = Literal["resolve", "delete"]


def get_role(db: Session, doc: Document, user: User) -> Role | None:
    """Return the user's role on the document, or None if they have no access."""
    if doc.owner_id == user.id:
        return "owner"
    share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == doc.id, DocumentShare.user_id == user.id
        )
    )
    return share.role.value if share else None  # type: ignore[return-value]


def can_view(role: Role | None) -> bool:
    """Anyone with a role can view."""
    return role is not None


def can_comment(role: Role | None) -> bool:
    """Everyone except viewers can comment."""
    return role in ("owner", "editor", "commenter")


def can_edit(role: Role | None) -> bool:
    """Owners and editors can edit."""
    return role in ("owner", "editor")


def is_owner(role: Role | None) -> bool:
    """Sharing, deleting and transferring ownership are owner-only."""
    return role == "owner"


_CHECKS: dict[Need, Callable[[Role | None], bool]] = {
    "view": can_view,
    "comment": can_comment,
    "edit": can_edit,
    "share": is_owner,
    "delete": is_owner,
    "transfer": is_owner,
}


def comment_action_allowed(role: Role, is_author: bool, action: CommentAction) -> bool:
    """Editors and the owner may resolve any comment; only the owner may delete any comment.
    Authors may always resolve or delete their own."""
    if is_author:
        return True
    return can_edit(role) if action == "resolve" else is_owner(role)


def check_comment_action(role: Role, is_author: bool, action: CommentAction) -> None:
    """403 unless comment_action_allowed."""
    if not comment_action_allowed(role, is_author, action):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You do not have permission to {action} this comment")


def load_doc_for(db: Session, doc_id: str, user: User, need: Need) -> tuple[Document, Role]:
    """Load a document the user is allowed to act on, returning it with their role.

    404 if the doc does not exist or the user has no access (so IDs do not leak);
    403 if they can see it but lack the needed permission.
    """
    doc = db.get(Document, doc_id)
    role = get_role(db, doc, user) if doc else None
    if doc is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if not _CHECKS[need](role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You do not have permission to {need} this document")
    return doc, role
