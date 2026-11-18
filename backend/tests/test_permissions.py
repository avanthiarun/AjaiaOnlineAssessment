"""Every cell of the role x action tables in app/permissions.py's docstring."""

import pytest
from fastapi import HTTPException

from app.db import SessionLocal
from app.models import Document, DocumentShare, ShareRole, User
from app.permissions import CommentAction, Need, Role, check_comment_action, comment_action_allowed, load_doc_for

ROLES: tuple[Role, ...] = ("owner", "editor", "commenter", "viewer")
TABLE: dict[Need, tuple[bool, bool, bool, bool]] = {
    # action      owner  editor  commenter  viewer
    "view":      (True,  True,   True,      True),
    "comment":   (True,  True,   True,      False),
    "edit":      (True,  True,   False,     False),
    "share":     (True,  False,  False,     False),
    "delete":    (True,  False,  False,     False),
    "transfer":  (True,  False,  False,     False),
}  # fmt: skip
CELLS = [(need, role, allowed) for need, row in TABLE.items() for role, allowed in zip(ROLES, row, strict=True)]


def make_doc(owner: User, member: User | None = None, role: Role | None = None) -> str:
    """Create a document owned by `owner`, optionally shared with `member` as `role`."""
    with SessionLocal() as db:
        doc = Document(owner_id=owner.id, title="Table test")
        db.add(doc)
        db.flush()
        if member and role:
            db.add(DocumentShare(document_id=doc.id, user_id=member.id, role=ShareRole(role)))
        db.commit()
        return doc.id


@pytest.mark.parametrize(("need", "role", "allowed"), CELLS, ids=[f"{r}-{n}" for n, r, _ in CELLS])
def test_role_can_or_cannot(users: dict[str, User], need: Need, role: Role, allowed: bool) -> None:
    owner, member = users["alice"], users["bob"]
    actor = owner if role == "owner" else member
    doc_id = make_doc(owner, None if role == "owner" else member, None if role == "owner" else role)

    with SessionLocal() as db:
        if allowed:
            assert load_doc_for(db, doc_id, actor, need)[1] == role
        else:
            with pytest.raises(HTTPException) as denied:
                load_doc_for(db, doc_id, actor, need)
            assert denied.value.status_code == 403


COMMENT_TABLE: dict[CommentAction, tuple[bool, bool, bool, bool]] = {
    # on someone else's comment   owner  editor  commenter  viewer
    "resolve":                   (True,  True,   False,     False),
    "delete":                    (True,  False,  False,     False),
}  # fmt: skip
COMMENT_CELLS = [
    (action, role, is_author, is_author or allowed)  # authors may always act on their own comments
    for action, row in COMMENT_TABLE.items()
    for role, allowed in zip(ROLES, row, strict=True)
    for is_author in (False, True)
]


@pytest.mark.parametrize(
    ("action", "role", "is_author", "allowed"),
    COMMENT_CELLS,
    ids=[f"{r}-{a}-{'own' if own else 'others'}" for a, r, own, _ in COMMENT_CELLS],
)
def test_comment_actions(action: CommentAction, role: Role, is_author: bool, allowed: bool) -> None:
    assert comment_action_allowed(role, is_author, action) is allowed
    if allowed:
        check_comment_action(role, is_author, action)
    else:
        with pytest.raises(HTTPException) as denied:
            check_comment_action(role, is_author, action)
        assert denied.value.status_code == 403


@pytest.mark.parametrize("need", TABLE)
def test_users_without_access_get_404_for_every_action(users: dict[str, User], need: Need) -> None:
    doc_id = make_doc(users["alice"])

    with SessionLocal() as db, pytest.raises(HTTPException) as hidden:
        load_doc_for(db, doc_id, users["carol"], need)
    assert hidden.value.status_code == 404
