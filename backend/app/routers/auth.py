"""Login, logout and current-user endpoints (mocked auth, see app/auth/session.py)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.passwords import verify_password
from app.auth.session import login_user, logout_user
from app.db import get_db
from app.models import User
from app.schemas.user import DemoUserOut, LoginIn, UserOut

DEMO_EMAIL_DOMAIN = "@ajaia.test"

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> User:
    """Sign in with email + password. Unknown email and wrong password look the same."""
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    login_user(request, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    """Clear the session cookie."""
    logout_user(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the signed-in user."""
    return user


@router.get("/demo-users", response_model=list[DemoUserOut])
def demo_users(db: Session = Depends(get_db)) -> list[User]:
    """List demo accounts for the login page's one-click "Sign in as" buttons."""
    query = select(User).where(User.email.endswith(DEMO_EMAIL_DOMAIN)).order_by(User.email)
    return list(db.scalars(query))
