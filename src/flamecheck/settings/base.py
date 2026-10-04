"""
Base settings for the FlameCheck Django project.

Environment-specific settings live in ``flamecheck.settings.development`` and
``flamecheck.settings.production`` and are selected via ``DJANGO_SETTINGS_MODULE``
(default: ``flamecheck.settings`` -> development).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[3]

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")
environ.Env.read_env(BASE_DIR / ".env.dev")

ENV = env.str("ENV", "development")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = env.str("DJANGO_SECRET_KEY", "insecure-development-only-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=ENV != "production")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # Generic OpenID Connect provider (Keycloak & co. configure themselves as
    # sub-providers of it, keyed by their ``provider_id``).
    "allauth.socialaccount.providers.openid_connect",
    "django_filters",
    "corsheaders",
]

LOCAL_APPS = [
    "users",
    "substances",
    "analyses",
    "config",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "flamecheck.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "users.context_processors.allauth_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "flamecheck.wsgi.application"
ASGI_APPLICATION = "flamecheck.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# The default backend is SQLite (``<repo>/db.sqlite3``) so the project runs with
# zero external services. Any other engine can be selected by setting
# ``DATABASE_URL`` (e.g. in ``.env`` / the container environment):
#
#   SQLite (default):  sqlite:////absolute/path/to/db.sqlite3
#   PostgreSQL:        postgres://user:pass@host:5432/flamecheck
#
# ``env.db()`` maps the URL to Django's ``DATABASES`` dict, so the same
# settings work for both engines. See ``.env-template`` for an example.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    ),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = env.bool("DJANGO_ATOMIC_REQUESTS", default=True)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# In-process database-backup scheduler (config app). Set to False to rely on
# an external cron/systemd timer running ``manage.py backup_database``.
DATABASE_BACKUP_SCHEDULER = env.bool("DATABASE_BACKUP_SCHEDULER", default=True)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "frontend-index"
LOGOUT_REDIRECT_URL = "frontend-index"
ACCOUNT_ALLOW_REGISTRATION = env.bool("ACCOUNT_ALLOW_REGISTRATION", default=False)
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ADAPTER = "users.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "users.adapters.SocialAccountAdapter"
# OAuth identity providers (django-allauth). A JSON object keyed by provider id,
# e.g. {"google": {"APP": {"client_id": "...", "secret": "...", "key": ""}}}.
#
# OpenID Connect providers (Keycloak & co.) use the generic ``openid_connect``
# provider; each realm is one entry in the ``APPS`` list whose ``provider_id``
# is what the login button links to (``/{provider_id}/login/``). Example (a
# Keycloak realm "flamecheck"):
#   {"openid_connect": {"APPS": [{
#       "provider_id": "keycloak", "name": "Keycloak",
#       "client_id": "flamecheck", "secret": "<realm client secret>",
#       "settings": {"server_url": "https://keycloak.example.com/realms/flamecheck"}
#   }]}}
# The realm's valid redirect URI must be
#   https://<host>/<provider_id>/login/callback/
# Empty by default: OAuth registration only offers buttons for configured providers.
SOCIALACCOUNT_PROVIDERS = env.json("SOCIALACCOUNT_PROVIDERS", default={})
# A plain link to the provider login URL (e.g. /google/login/) starts the
# provider flow immediately instead of rendering an intermediate confirm page,
# which is what the SPA login button expects.
SOCIALACCOUNT_LOGIN_ON_GET = True

# ---------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------
# The console backend is the default *development* choice (see development.py);
# production sets a real SMTP backend. These defaults keep the address stable.
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="FlameCheck <no-reply@flamecheck.local>")
EMAIL_SUBJECT_PREFIX = env.str("EMAIL_SUBJECT_PREFIX", default="[FlameCheck] ")
# How long a self-registration e-mail-confirmation link stays valid (seconds).
EMAIL_VERIFICATION_TOKEN_MAX_AGE = env.int("EMAIL_VERIFICATION_TOKEN_MAX_AGE", default=48 * 3600)

# ---------------------------------------------------------------------------
# JWT / token auth
# ---------------------------------------------------------------------------
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=30)
JWT_REFRESH_TOKEN_LIFETIME_DAYS = env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=14)
JWT_SIGNING_KEY = env.str("JWT_SIGNING_KEY", default=SECRET_KEY)
JWT_AUDIENCE = env.str("JWT_AUDIENCE", default="flamecheck-api")
JWT_ISSUER = env.str("JWT_ISSUER", default="flamecheck")
# Number of failed logins before a temporary lockout
LOGIN_MAX_ATTEMPTS = env.int("LOGIN_MAX_ATTEMPTS", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=300)

# ---------------------------------------------------------------------------
# External reference links
# ---------------------------------------------------------------------------
# Base URL for PubChem compound pages. A substance's PubChem CID is appended to
# this to form the page URL, e.g. ``PUBCHEM_BASE_URL + "238914022"``. Stored
# centrally so every app that links to PubChem reuses the same base.
PUBCHEM_BASE_URL = env.str("PUBCHEM_BASE_URL", default="https://pubchem.ncbi.nlm.nih.gov/compound/")

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The Vite build runs with ``--base /static/`` (see frontend/package.json), so
# the built index.html references its chunks as /static/assets/*. Pointing the
# staticfiles dir at frontend/dist maps dist/assets/* to /static/assets/* and
# dist/favicon.* to /static/favicon.* exactly as the built page expects.
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Django Ninja API
# ---------------------------------------------------------------------------
API_PREFIX = "/api/v1"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env.str("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        # dedicated logger for audit-relevant events (submissions, admin changes)
        "flamecheck.audit": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Project specific
# ---------------------------------------------------------------------------
FIXTURES: list[str] = []
# Directory holding importable ion / substance catalogs (CSV or JSON)
CATALOG_DIR = BASE_DIR / "packages" / "substances" / "data"

APPEND_SLASH = False
