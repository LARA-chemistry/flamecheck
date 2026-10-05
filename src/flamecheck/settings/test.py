"""Test settings for FlameCheck."""

from .base import *  # noqa: F403

# Fast password hasher for tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use the same (database) cache backend as production so the rate-limit code
# paths are exercised against a real table, not the in-memory stand-in.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "flamecheck_cache",
        "TIMEOUT": 300,
    }
}

# The in-process backup scheduler must not run during tests.
DATABASE_BACKUP_SCHEDULER = False
