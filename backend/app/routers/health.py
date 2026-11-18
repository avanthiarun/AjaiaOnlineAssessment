"""Liveness/readiness endpoint used by Railway's healthcheck."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=None)
def health(db: Session = Depends(get_db)) -> dict[str, str] | JSONResponse:
    """Return ok if the app is up and the database answers SELECT 1."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
    return {"status": "ok"}
