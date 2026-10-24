"""Consistent error envelope: {"error": {"code", "message", "fields"}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import AutoReconnect, ConnectionFailure, ExecutionTimeout, NetworkTimeout, ServerSelectionTimeoutError
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException


log = logging.getLogger("annkut.errors")

DB_UNAVAILABLE = (ServerSelectionTimeoutError, AutoReconnect, ConnectionFailure, NetworkTimeout, ExecutionTimeout)


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields
        self.details = details


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "NOT_FOUND", f"{what} not found.")


def _body(code: str, message: str, fields=None, details=None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if fields:
        err["fields"] = fields
    if details:
        err["details"] = details
    return {"error": err}


_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def _field_name(loc: tuple) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "request"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code, content=_body(exc.code, exc.message, exc.fields, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields: dict[str, str] = {}
        for e in exc.errors():
            msg = e.get("msg", "Invalid value")
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, ") :]
            fields.setdefault(_field_name(tuple(e.get("loc", ()))), msg)
        return JSONResponse(
            status_code=422, content=_body("VALIDATION_ERROR", "Please check the highlighted fields.", fields)
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=_body(code, message), headers=exc.headers)

    @app.exception_handler(RateLimitExceeded)
    async def _rate(_: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=_body("RATE_LIMITED", "Too many requests right now. Please wait a moment and try again."),
            headers={"Retry-After": "30"},
        )

    for exc_type in DB_UNAVAILABLE:

        @app.exception_handler(exc_type)
        async def _db_down(request: Request, exc: Exception):
            log.error("Database unavailable on %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(
                status_code=503,
                content=_body("SERVICE_UNAVAILABLE", "We can't reach the database right now. Please try again in a moment."),
                headers={"Retry-After": "5"},
            )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        log.exception("Unhandled error %s on %s %s", request_id, request.method, request.url.path)
        details = {"request_id": request_id} if request_id else None
        return JSONResponse(
            status_code=500,
            content=_body("INTERNAL_ERROR", "Something went wrong on our side. Please try again.", details=details),
        )
