from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from ..config import get_settings


def to_utc_from_local(value: datetime) -> datetime:
    """Naive datetimes are wall-clock times in APP_TIMEZONE. Aware ones are converted to UTC.

    Rejects wall-clock times that don't exist because of a DST spring-forward gap.
    """
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(microsecond=0)
    tz = get_settings().tz
    local = value.replace(tzinfo=tz, microsecond=0)
    as_utc = local.astimezone(UTC)
    if as_utc.astimezone(tz).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError("That time doesn't exist on this date (clocks moved forward). Pick another time.")
    return as_utc


class _Times(BaseModel):
    @field_validator("clock_in", "clock_out", mode="after", check_fields=False)
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else to_utc_from_local(v)


class ManualSessionIn(_Times):
    clock_in: datetime
    clock_out: datetime
    reason: str | None = Field(default=None, max_length=500)
    confirm_overlap: bool = False


class SessionUpdateIn(_Times):
    clock_in: datetime | None = None
    clock_out: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)
    confirm_overlap: bool = False


class PreviewIn(_Times):
    clock_in: datetime
    clock_out: datetime | None = None
    session_id: str | None = None


class CorrectionIn(SessionUpdateIn):
    reason: str = Field(min_length=1, max_length=500)


class MarkReviewedIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
