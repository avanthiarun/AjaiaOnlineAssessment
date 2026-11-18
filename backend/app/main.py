"""FastAPI application: middleware, API routers and the built frontend (SPA)."""

import logging
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import SessionLocal, engine, init_db
from app.routers import auth, comments, documents, health, presence, shares, uploads, versions
from app.services.seed import seed_demo_users

STATIC_DIR = Path(__file__).parent / "static"
SESSION_MAX_AGE = 7 * 24 * 60 * 60
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # 'unsafe-inline' styles are needed because ProseMirror/TipTap set inline style attributes.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# Production is HTTPS-only (Railway terminates TLS), so tell browsers never to use plain HTTP.
# Not sent in development, where the app runs on http://localhost.
HSTS_HEADER = "max-age=31536000"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("app")

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables and optionally seed demo data on startup."""
    # Only the environment and DB dialect: never the URL, which contains the password.
    logger.info("Starting Ajaia Docs (env=%s, db=%s)", settings.env, engine.dialect.name)
    init_db()
    if settings.seed_on_start:
        with SessionLocal() as db:
            seed_demo_users(db)
    yield


# Interactive API docs only in development: production has no use for them, and its CSP
# (script-src 'self') would block Swagger UI's CDN scripts anyway.
_docs = not settings.is_production
app = FastAPI(
    title="Ajaia Docs",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=settings.is_production,
)


# Registered before security_headers so it runs inside it: the 500 still gets the headers.
# A middleware (not @app.exception_handler(Exception)) because Starlette re-raises after such a
# handler, which would make uvicorn log every traceback a second time.
@app.middleware("http")
async def catch_unhandled_errors(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log unexpected errors with a traceback (method + path only, never bodies) and return a generic 500."""
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach basic security headers to every response."""
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = HSTS_HEADER
    return response


for module in (health, auth, documents, shares, presence, versions, comments, uploads):
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
