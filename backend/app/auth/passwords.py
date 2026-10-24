"""Password policy and Argon2id hashing."""

import hashlib
import logging
import re
from functools import lru_cache

import anyio
import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from ..config import get_settings
from ..enums import PASSWORD_MIN_LENGTH, shared_file

log = logging.getLogger(__name__)

# argon2-cffi defaults to Argon2id with RFC 9106 low-memory parameters.
_hasher = PasswordHasher()

MIN_LENGTH = PASSWORD_MIN_LENGTH  # shared/enums.json, same value the frontend uses
_SPECIAL = re.compile(r"[^A-Za-z0-9]")
_LEET = str.maketrans({"@": "a", "4": "a", "0": "o", "1": "i", "!": "i", "3": "e", "$": "s", "5": "s", "7": "t"})


@lru_cache
def _common_passwords() -> frozenset[str]:
    # Shared with the frontend checklist: shared/common_passwords.txt
    path = shared_file("common_passwords.txt")
    lines = (ln.strip().lower() for ln in path.read_text().splitlines())
    return frozenset(ln for ln in lines if ln and not ln.startswith("#"))


def _core(pw: str) -> str:
    """Lowercase with leading/trailing digits and symbols stripped: 'Welcome2024!' -> 'welcome'."""
    return re.sub(r"^[^a-z]+|[^a-z]+$", "", pw.lower())


def is_common_password(pw: str) -> bool:
    common = _common_passwords()
    lowered = pw.lower()
    candidates = {lowered, _core(pw), lowered.translate(_LEET), _core(pw).translate(_LEET), _core(lowered.translate(_LEET))}
    return any(c and c in common for c in candidates)


def password_problems(pw: str, username: str | None = None) -> list[str]:
    """Human-readable problems with a password. Empty list means it passes the policy."""
    problems = []
    if len(pw) < MIN_LENGTH:
        problems.append(f"Use at least {MIN_LENGTH} characters.")
    if not (re.search(r"[a-z]", pw) and re.search(r"[A-Z]", pw)):
        problems.append("Use both uppercase and lowercase letters.")
    if not re.search(r"\d", pw):
        problems.append("Add at least one number.")
    if not _SPECIAL.search(pw):
        problems.append("Add at least one special character.")
    if is_common_password(pw):
        problems.append("This password is too common. Choose something harder to guess.")
    if username and len(username) >= 3 and username.lower() in pw.lower():
        problems.append("Don't include your username in your password.")
    return problems


async def is_pwned(pw: str) -> bool:
    """HaveIBeenPwned k-anonymity range check. Fails open (returns False) on network errors."""
    sha1 = hashlib.sha1(pw.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}", headers={"Add-Padding": "true"}
            )
            r.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("HIBP check skipped: %s", exc)
        return False
    for line in r.text.splitlines():
        h, _, count = line.partition(":")
        if h == suffix and int(count or 0) > 0:
            return True
    return False


def hash_password(pw: str) -> str:
    return _hasher.hash(pw)


def verify_password(pw: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, pw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# Used to equalise timing when a username doesn't exist.
DUMMY_HASH = _hasher.hash("dummy-password-for-timing-only")


# Each Argon2 operation takes ~40 ms of CPU and 64 MiB of RAM. Running them inline would block the
# event loop, and running hundreds at once could exhaust memory. So they run in worker threads,
# at most HASH_CONCURRENCY at a time per process; extra requests wait their turn.
_limiter: anyio.CapacityLimiter | None = None


def _hash_limiter() -> anyio.CapacityLimiter:
    global _limiter
    if _limiter is None:
        _limiter = anyio.CapacityLimiter(get_settings().hash_concurrency)
    return _limiter


async def hash_password_async(pw: str) -> str:
    return await anyio.to_thread.run_sync(hash_password, pw, limiter=_hash_limiter())


async def verify_password_async(pw: str, password_hash: str) -> bool:
    return await anyio.to_thread.run_sync(verify_password, pw, password_hash, limiter=_hash_limiter())
