"""CSRF protection for cookie-authenticated requests: double-submit token plus an Origin check."""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import get_settings
from .tokens import CSRF_COOKIE, CSRF_HEADER

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _reject(message: str) -> JSONResponse:
    return JSONResponse(status_code=403, content={"error": {"code": "CSRF_FAILED", "message": message}})


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS or not request.url.path.startswith("/api/"):
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin:
            allowed = set(get_settings().allowed_origins)
            own = f"{request.url.scheme}://{request.url.netloc}"
            if origin != own and origin not in allowed:
                return _reject("Request origin not allowed.")

        cookie = request.cookies.get(CSRF_COOKIE)
        header = request.headers.get(CSRF_HEADER)
        if not cookie or not header or not secrets.compare_digest(cookie, header):
            return _reject("Your session needs a refresh. Reload the page and try again.")
        return await call_next(request)
