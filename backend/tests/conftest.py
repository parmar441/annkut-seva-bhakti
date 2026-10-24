import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("APP_TIMEZONE", "America/New_York")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-0123456789")

from datetime import UTC, datetime  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app import common  # noqa: E402
from app.db import ensure_indexes, set_database  # noqa: E402
from app.enums import Role  # noqa: E402
from app.main import create_app  # noqa: E402
from app.users.service import create_user  # noqa: E402

STRONG_PASSWORD = "Seva-Kitchen-42!"
BASE_URL = "http://testserver"


@pytest.fixture
async def db():
    database = AsyncMongoMockClient(tz_aware=True)["annkut_test"]
    await ensure_indexes(database)
    # mongomock ignores partialFilterExpression, so this index would wrongly make user_id unique for
    # every session. Real MongoDB enforces it; the service also pre-checks for an active session.
    await database.seva_sessions.drop_index("one_active_session_per_user")
    set_database(database)
    yield database
    common.freeze_now(None)


@pytest.fixture
def clock():
    """Pin the server's seva clock: clock.set(datetime(...)), clock.advance(minutes=...)."""

    class Clock:
        now: datetime | None = None

        def set(self, value: datetime) -> datetime:
            self.now = value if value.tzinfo else value.replace(tzinfo=UTC)
            common.freeze_now(self.now)
            return self.now

        def advance(self, **kw) -> datetime:
            from datetime import timedelta

            return self.set(self.now + timedelta(**kw))

    c = Clock()
    yield c
    common.freeze_now(None)


class ApiClient(httpx.AsyncClient):
    """Test client that does the CSRF double-submit like the real frontend."""

    async def csrf(self) -> str:
        r = await self.get("/api/auth/csrf")
        return r.json()["csrf_token"]

    async def request(self, method, url, **kw):
        if method.upper() not in ("GET", "HEAD", "OPTIONS"):
            token = self.cookies.get("csrf_token")
            if token is None and not kw.pop("_skip_csrf", False):
                token = (await super().request("GET", "/api/auth/csrf")).json()["csrf_token"]
            headers = dict(kw.pop("headers", None) or {})
            if token and "X-CSRF-Token" not in headers:
                headers["X-CSRF-Token"] = token
            kw["headers"] = headers
        return await super().request(method, url, **kw)

    async def login(self, username: str, password: str = STRONG_PASSWORD) -> httpx.Response:
        r = await self.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return r


@pytest.fixture
def app(db):
    return create_app(start_background=False)


@pytest.fixture
def make_client(app):
    clients: list[ApiClient] = []

    def _make() -> ApiClient:
        c = ApiClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL)
        clients.append(c)
        return c

    yield _make


@pytest.fixture
async def client(make_client):
    async with make_client() as c:
        yield c


@pytest.fixture
def make_user(db):
    async def _make(username: str, role: Role = Role.USER, mandal_name="Edison", mandal_type="Yuvti", full_name=None):
        return await create_user(
            db,
            full_name=full_name or username.title(),
            username=username,
            password=STRONG_PASSWORD,
            mandal_name=mandal_name,
            mandal_type=mandal_type,
            role=role,
        )

    return _make


@pytest.fixture
async def user_client(make_client, make_user):
    await make_user("anjali.p", full_name="Anjali Patel")
    async with make_client() as c:
        await c.login("anjali.p")
        yield c


@pytest.fixture
async def admin_client(make_client, make_user):
    await make_user("organizer", role=Role.ADMIN, full_name="Edison Organizer")
    async with make_client() as c:
        await c.login("organizer")
        yield c
