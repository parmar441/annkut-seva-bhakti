import asyncio
import contextlib
import logging
import uuid
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from .admin.router import router as admin_router
from .auth.csrf import CSRFMiddleware
from .auth.router import router as auth_router
from .config import get_settings
from .db import close_db, ensure_indexes, get_db, is_in_memory
from .errors import install_error_handlers
from .meta.router import router as meta_router
from .ratelimit import limiter
from .sessions.router import router as sessions_router
from .sessions.service import sweep_missing_clock_outs

log = logging.getLogger("annkut")


async def _prepare_database() -> None:
    """Create indexes (and demo data in in-memory mode), retrying until the database is reachable.

    Runs in the background so a slow or briefly unavailable database never stops the app from starting.
    """
    settings = get_settings()
    delay = 2
    while True:
        try:
            await ensure_indexes(get_db())
            if is_in_memory() and settings.environment != "production":
                from .scripts.seed import seed_database

                if not await get_db().users.count_documents({}):
                    await seed_database(get_db())
                log.warning("Using the in-memory demo database with sample data. Data is lost on restart.")
            log.info("Database ready")
            return
        except Exception:
            log.exception("Database not ready; retrying in %ss", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


async def _sweep_forever(interval: int) -> None:
    while True:
        try:
            flagged = await sweep_missing_clock_outs(get_db())
            if flagged:
                log.info("Flagged %d sessions with a missing clock-out", flagged)
        except Exception:  # keep the loop alive; the next sweep retries
            log.exception("Missing clock-out sweep failed")
        await asyncio.sleep(interval)


def create_app(*, start_background: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        tasks: list[asyncio.Task] = []
        if start_background:
            tasks.append(asyncio.create_task(_prepare_database()))
            tasks.append(asyncio.create_task(_sweep_forever(settings.flag_sweep_seconds)))
        yield
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if start_background:
            close_db()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="1.0.0",
        description="Volunteer seva hour tracking. Auth uses HttpOnly cookies; mutating requests need the "
        "X-CSRF-Token header to match the csrf_token cookie (GET /api/auth/csrf).",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    install_error_handlers(app)

    # Order: Starlette runs the last-added middleware first. CORS must wrap CSRF so rejections carry CORS headers.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(auth_router)
    app.include_router(meta_router)
    app.include_router(sessions_router)
    app.include_router(admin_router)

    @app.get("/api/health", tags=["meta"])
    @limiter.exempt
    async def health():
        """Liveness: the process is up."""
        return {"status": "ok"}

    @app.get("/api/health/ready", tags=["meta"])
    @limiter.exempt
    async def ready():
        """Readiness: the database answers within 2 seconds."""
        try:
            await asyncio.wait_for(get_db().command("ping"), timeout=2)
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unreachable"})
        return {"status": "ok", "database": "ok"}

    if settings.static_dir:
        _serve_frontend(app, Path(settings.static_dir))

    return app


def _serve_frontend(app: FastAPI, root: Path) -> None:
    """Serve the built React app on the same origin as the API, so auth cookies stay first-party."""
    index = root / "index.html"
    if not index.is_file():
        log.warning("STATIC_DIR %s has no index.html; not serving the frontend", root)
        return
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    @limiter.exempt
    async def spa(path: str, request: Request):
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND", "message": "Not found."}})
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root.resolve()):
            return FileResponse(candidate)
        # Client-side routes (/history, /admin/...) all load index.html; never cache it.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
