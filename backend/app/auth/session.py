"""Cookie-session login helpers.

Tradeoff: this is deliberately lightweight, mocked auth for a take-home. Users are the
seeded demo accounts, there is no signup, password reset, rate limiting or MFA, and the
session is a signed cookie holding only the user id. Good enough to demo ownership and
sharing; a real product would use a proper identity provider.
"""

from fastapi import Request

from app.models import User

SESSION_USER_KEY = "user_id"


def login_user(request: Request, user: User) -> None:
    """Start a fresh session for the user (clearing any previous session data)."""
    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id


def logout_user(request: Request) -> None:
    """End the current session."""
    request.session.clear()
