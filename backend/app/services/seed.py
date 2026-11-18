"""Idempotent demo data so reviewers can try login and sharing immediately."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.models import Document, DocumentShare, ShareRole, User

DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    ("alice@ajaia.test", "Alice Owner"),
    ("bob@ajaia.test", "Bob Collaborator"),
    ("carol@ajaia.test", "Carol Viewer"),
]
WELCOME_HTML = (
    "<h1>Welcome to Ajaia Docs</h1>"
    "<p><strong>This document is shared with Bob (editor) and Carol (viewer).</strong></p>"
    "<ul>"
    "<li>Edit the text and it saves automatically</li>"
    "<li>Use the toolbar for headings, bold, italic, underline and lists</li>"
    "<li>Share it with another user from the Share button</li>"
    "</ul>"
)


def seed_demo_users(db: Session) -> None:
    """Create the demo users, plus a shared welcome doc if Alice has no documents."""
    users: dict[str, User] = {}
    for email, name in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=name, password_hash=hash_password(DEMO_PASSWORD))
            db.add(user)
        users[email] = user
    db.flush()

    alice = users["alice@ajaia.test"]
    if not db.scalar(select(func.count()).select_from(Document).where(Document.owner_id == alice.id)):
        doc = Document(owner=alice, title="Welcome to Ajaia Docs", content_html=WELCOME_HTML)
        doc.shares = [
            DocumentShare(user=users["bob@ajaia.test"], role=ShareRole.EDITOR),
            DocumentShare(user=users["carol@ajaia.test"], role=ShareRole.VIEWER),
        ]
        db.add(doc)
    db.commit()
