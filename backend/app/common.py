"""Small helpers shared across modules."""

from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId

from .errors import not_found


_frozen_now: datetime | None = None


def utcnow() -> datetime:
    """Server clock. All clock-in/out timestamps come from here. Whole seconds, UTC."""
    if _frozen_now is not None:
        return _frozen_now
    return datetime.now(UTC).replace(microsecond=0)


def freeze_now(value: datetime | None) -> None:
    """Tests only: pin the seva clock. Token expiry always uses the real clock."""
    global _frozen_now
    _frozen_now = value.astimezone(UTC).replace(microsecond=0) if value else None


def parse_oid(value: str, what: str = "Resource") -> ObjectId:
    """Parse an ObjectId from a path parameter. Malformed ids are reported as 404, not 422."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise not_found(what) from None


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def page_params(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    return (page - 1) * page_size, page_size


def page_meta(page: int, page_size: int, total: int) -> dict:
    return {"page": page, "page_size": page_size, "total": total, "pages": max(1, -(-total // page_size))}
