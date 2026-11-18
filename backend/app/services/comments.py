"""Comment business logic. Plain comments only: suggestion mode (tracked changes) is out of scope.

Bodies are stored and returned exactly as typed (never sanitized into HTML, never rendered as
HTML); the frontend escapes them by rendering them as text.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Comment, Document, User
from app.permissions import CommentAction, Role, check_comment_action, comment_action_allowed
from app.schemas.comment import CommentOut


def to_out(comment: Comment, user: User, role: Role) -> CommentOut:
    """Serialize a comment with the caller's permissions on it."""
    is_author = comment.author_id == user.id
    return CommentOut.model_validate(
        {
            "id": comment.id,
            "author": comment.author,
            "quote": comment.quote,
            "body": comment.body,
            "resolved": comment.resolved,
            "created_at": comment.created_at,
            "can_resolve": comment_action_allowed(role, is_author, "resolve"),
            "can_delete": comment_action_allowed(role, is_author, "delete"),
        }
    )


def list_comments(db: Session, doc: Document) -> list[Comment]:
    """All comments on a document, oldest first, with authors loaded."""
    return list(
        db.scalars(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(Comment.document_id == doc.id)
            .order_by(Comment.created_at)
        )
    )


def create_comment(db: Session, doc: Document, author: User, quote: str, body: str) -> Comment:
    """Add a comment (the caller already passed the "comment" permission check)."""
    comment = Comment(document_id=doc.id, author=author, quote=quote, body=body)
    db.add(comment)
    db.commit()
    return comment


def get_for_action(
    db: Session, doc: Document, comment_id: str, user: User, role: Role, action: CommentAction
) -> Comment:
    """Load a comment of this document that the user may resolve/delete (404, then 403)."""
    comment = db.get(Comment, comment_id)
    if comment is None or comment.document_id != doc.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    check_comment_action(role, comment.author_id == user.id, action)
    return comment


def set_resolved(db: Session, comment: Comment, resolved: bool) -> Comment:
    """Resolve or reopen a comment."""
    comment.resolved = resolved
    db.commit()
    return comment


def delete_comment(db: Session, comment: Comment) -> None:
    """Delete a comment."""
    db.delete(comment)
    db.commit()
