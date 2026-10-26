"""Shared enums. The values live in shared/enums.json so the frontend uses the same list."""

import json
import os
from enum import Enum
from pathlib import Path


def shared_file(name: str) -> Path:
    """Locate a file in the repo's shared/ directory (or SHARED_DIR, e.g. inside Docker)."""
    candidates = [
        Path(os.environ["SHARED_DIR"]) if os.environ.get("SHARED_DIR") else None,
        Path(__file__).resolve().parents[2] / "shared",
        Path(__file__).resolve().parents[1] / "shared",
    ]
    for c in candidates:
        if c and (c / name).is_file():
            return c / name
    raise RuntimeError(f"shared/{name} not found; set SHARED_DIR")


_DATA = json.loads(shared_file("enums.json").read_text())

MandalName = Enum("MandalName", {v.upper().replace(" ", "_"): v for v in _DATA["mandal_names"]}, type=str)
MandalType = Enum("MandalType", {v.upper(): v for v in _DATA["mandal_types"]}, type=str)

MANDAL_NAMES: list[str] = list(_DATA["mandal_names"])
MANDAL_TYPES: list[str] = list(_DATA["mandal_types"])
PASSWORD_MIN_LENGTH: int = int(_DATA["password_min_length"])
SECURITY_QUESTIONS: list[str] = list(_DATA["security_questions"])
SECURITY_ANSWER_MIN_LENGTH: int = int(_DATA["security_answer_min_length"])


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class SessionFlag(str, Enum):
    MISSING_CLOCK_OUT = "missing_clock_out"
    OVERLAP = "overlap"
    LONG_SESSION = "long_session"
    MANUAL_ENTRY = "manual_entry"


class SessionSource(str, Enum):
    CLOCK = "clock"
    MANUAL = "manual"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    CORRECT = "correct"
    REVIEW = "review"
    DELETE = "delete"
    RESTORE = "restore"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    RESET_ISSUED = "reset_issued"
    PASSWORD_RESET = "password_reset"


assert {f.value for f in SessionFlag} == set(_DATA["session_flags"])
