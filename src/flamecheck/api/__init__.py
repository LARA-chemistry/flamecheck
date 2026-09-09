"""Top-level Django Ninja API for FlameCheck."""

from __future__ import annotations

from django.conf import settings
from ninja import NinjaAPI
from users.api.jwt_auth import JWTBearerAuth

api = NinjaAPI(
    title="FlameCheck API",
    version="1.0.0",
    description="REST API for the inorganic qualitative analysis submission system.",
    auth=JWTBearerAuth(),
    urls_namespace="api",
    docs_url="/docs" if settings.DEBUG else None,
)

# Auth / user endpoints (login, refresh, logout, /me)
from users.api.views import router as auth_router  # noqa: E402

api.add_router("", auth_router)

# Substances (ions, substances)
from substances.api.views import router as substances_router  # noqa: E402

api.add_router("", substances_router)

# Student analysis endpoints
from analyses.api.student import router as student_router  # noqa: E402

api.add_router("", student_router)

# Assistant endpoints
from analyses.api.assistant import router as assistant_router  # noqa: E402

api.add_router("assistant", assistant_router)

# Admin endpoints
from analyses.api.admin import router as admin_router  # noqa: E402

api.add_router("admin", admin_router)
