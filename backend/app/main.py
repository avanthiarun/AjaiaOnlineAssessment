"""FastAPI application: middleware, API routers and the built frontend (SPA)."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.routers import auth, documents, health, shares, uploads
from app.services.seed import seed_demo_users

STATIC_DIR = Path(__file__).parent / "static"
SESSION_MAX_AGE = 7 * 24 * 60 * 60
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables and optionally seed demo data on startup."""
    init_db()
    if settings.seed_on_start:
        with SessionLocal() as db:
            seed_demo_users(db)
    yield


app = FastAPI(title="Ajaia Docs", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=settings.is_production,
)


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach basic security headers to every response."""
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


for module in (health, auth, documents, shares, uploads):
    app.include_router(module.router)


if (STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


def _spa_response(path: str) -> FileResponse:
    """Serve a top-level static file (e.g. favicon) if it exists, otherwise index.html."""
    candidate = (STATIC_DIR / path.lstrip("/")).resolve()
    if candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(STATIC_DIR / "index.html")


@app.exception_handler(StarletteHTTPException)
async def not_found_to_spa(request: Request, exc: StarletteHTTPException) -> Response:
    """Fall back to the SPA for unknown GET pages; /api and /assets keep JSON errors."""
    path = request.url.path
    if (
        exc.status_code == 404
        and request.method == "GET"
        and not path.startswith(("/api", "/assets"))
        and (STATIC_DIR / "index.html").is_file()
    ):
        return _spa_response(path)
    return await http_exception_handler(request, exc)
