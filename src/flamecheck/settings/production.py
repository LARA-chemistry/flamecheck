"""
Production settings for FlameCheck.

The database backend is inherited from :mod:`.base`: **SQLite by default**.
To run production on PostgreSQL, set ``DATABASE_URL`` in the environment
(e.g. via ``.env`` / the container) to a ``postgres://`` URL. No other change
is required — Django, migrations and the entrypoint are engine-agnostic.
"""

from .base import *  # noqa: F403
from .base import env

# DEBUG stays off by default in production; the staging compose sets
# DJANGO_DEBUG=true to enable the OpenAPI docs and debug features.
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Security hardening (assumes a TLS-terminating reverse proxy such as nginx)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
