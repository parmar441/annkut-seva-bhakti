from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings

_s = get_settings()

# Keyed by client IP. Behind a proxy, uvicorn's --proxy-headers / --forwarded-allow-ips must be set
# so request.client is the real visitor, not the proxy (see README "Running behind a proxy").
limiter = Limiter(
    key_func=get_remote_address,
    enabled=_s.rate_limit_enabled,
    storage_uri=_s.rate_limit_storage_uri,
    default_limits=[_s.api_rate_limit],
    headers_enabled=False,
    # If the limit store (e.g. Redis) is down, let requests through rather than failing them.
    swallow_errors=True,
)
