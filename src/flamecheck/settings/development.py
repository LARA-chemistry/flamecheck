"""Development settings for FlameCheck."""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# E-mail: print to the console (Django's "fake mail" backend).
# In development no real mail is sent; every outgoing message (e.g. the
# self-registration confirmation e-mail) is printed to the server console,
# including its full URL so it can be clicked locally.
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
