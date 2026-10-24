from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Annkut Seva Bhakti"
    environment: str = "development"

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "annkut_seva"

    # Auth
    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    # Origins allowed to call the API with cookies (CORS + Origin check for CSRF).
    cors_origins: list[str] = ["http://localhost:5173"]
    # Public URL of this deployment. Render sets RENDER_EXTERNAL_URL automatically.
    public_url: str | None = Field(default=None, validation_alias=AliasChoices("PUBLIC_URL", "RENDER_EXTERNAL_URL"))
    # Built frontend (frontend/dist) to serve from the same origin as the API, if present.
    static_dir: str | None = None

    mongo_max_pool_size: int = 200
    mongo_timeout_ms: int = 8000  # fail fast with a 503 instead of hanging when the DB is unreachable

    # Per-IP rate limits (slowapi syntax). Sized for a whole event on one Wi-Fi/NAT address:
    # 500+ volunteers signing in at once share a single public IP. Brute force is stopped by the
    # per-account failure limits below, not by these.
    rate_limit_enabled: bool = True
    rate_limit_storage_uri: str = "memory://"  # e.g. redis://redis:6379 to share limits across workers
    login_rate_limit: str = "1500/minute"
    register_rate_limit: str = "600/minute;3000/hour"
    refresh_rate_limit: str = "3000/minute"
    api_rate_limit: str = "6000/minute"  # every other endpoint, per IP

    # Brute-force protection: failed sign-ins within the window, per username+IP and per username.
    login_failure_window_minutes: int = 15
    login_failures_per_user_ip: int = 10
    login_failures_per_user: int = 50

    # Forgotten passwords: organizer-issued one-time codes.
    reset_code_minutes: int = 30
    reset_code_max_attempts: int = 5
    reset_request_rate_limit: str = "300/minute"
    reset_confirm_rate_limit: str = "300/minute"
    # Self-service reset with a security question: wrong answers per username before a pause.
    recovery_failures_per_user: int = 5
    recovery_failure_window_minutes: int = 15

    # Concurrent Argon2 operations per process (each needs ~64 MiB RAM and one CPU core).
    hash_concurrency: int = 8

    # Optional HaveIBeenPwned k-anonymity check
    hibp_enabled: bool = False

    # Time and seva rules
    app_timezone: str = "America/New_York"
    week_start: str = "sunday"  # sunday | monday
    long_session_hours: float = 16  # sessions longer than this are flagged
    max_session_hours: float = 24  # sessions longer than this are rejected
    missing_clock_out_hours: float = 12  # active sessions older than this are flagged
    flag_sweep_seconds: int = 600

    @field_validator("app_timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        ZoneInfo(v)
        return v

    @field_validator("week_start")
    @classmethod
    def _valid_week_start(cls, v: str) -> str:
        v = v.lower()
        if v not in ("sunday", "monday"):
            raise ValueError("week_start must be 'sunday' or 'monday'")
        return v

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.environment == "production":
            if self.jwt_secret.startswith("change-me") or len(self.jwt_secret) < 32:
                raise ValueError("Set JWT_SECRET to a random string of 32+ characters in production.")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production.")
            if self.mongo_url.startswith("mongomock://"):
                raise ValueError("The in-memory database can't be used in production.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        origins = list(self.cors_origins)
        if self.public_url:
            origins.append(self.public_url.rstrip("/"))
        return origins

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def week_start_weekday(self) -> int:
        """Python weekday() of the first day of the week (Mon=0 … Sun=6)."""
        return 6 if self.week_start == "sunday" else 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
