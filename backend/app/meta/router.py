from fastapi import APIRouter

from ..config import get_settings
from ..enums import MANDAL_NAMES, MANDAL_TYPES, PASSWORD_MIN_LENGTH, SECURITY_QUESTIONS

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/enums")
async def enums():
    s = get_settings()
    return {
        "mandal_names": MANDAL_NAMES,
        "mandal_types": MANDAL_TYPES,
        "password_min_length": PASSWORD_MIN_LENGTH,
        "security_questions": SECURITY_QUESTIONS,
        "timezone": s.app_timezone,
        "week_start": s.week_start,
        "long_session_hours": s.long_session_hours,
        "max_session_hours": s.max_session_hours,
    }
