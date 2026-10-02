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

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

# The in-process backup scheduler must not run during tests.
DATABASE_BACKUP_SCHEDULER = False
