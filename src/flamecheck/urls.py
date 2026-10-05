"""Root URL configuration for FlameCheck."""

from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

# Ninja mounts without a leading slash (Django's root resolver strips it).
# A trailing slash is required so removeprefix() leaves a clean remaining path.
api_url_path = settings.API_PREFIX.lstrip("/") + "/"
from flamecheck.api import api  # noqa: E402

# Unpack the ninja URL 3-tuple exactly once at module import time.
_ninja_patterns, _ninja_app_name, _ninja_namespace = api.urls

_FRONTEND_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html"


def frontend_index(request):
    """
    Serve the built Vue app entry point for SPA routes.

    The HTML shell is served with ``Cache-Control: no-cache`` so the browser
    always revalidates it and picks up new hashed asset references after a
    rebuild; the hashed assets themselves are safe to cache aggressively.
    """
    if _FRONTEND_INDEX.exists():
        response = HttpResponse(_FRONTEND_INDEX.read_text(encoding="utf-8"))
        response["Cache-Control"] = "no-cache"
        return response
    return HttpResponse(
        "FlameCheck API is running. The frontend has not been built yet "
        "(run `npm --prefix frontend run build` or `npm --prefix frontend run dev`).",
        content_type="text/plain",
    )


# The Django admin site lives at /admin-django/ (not /admin/) so it does not
# collide with the SPA admin panel route at /admin.
DjangoAdminPath = "admin-django/"


# Serve uploaded media (login branding, ...) in EVERY environment. The Docker
# production stack has no reverse proxy (gunicorn + WhiteNoise only serve the
# collected static files, not runtime uploads), so Django must serve media
# itself. The files are few and small (a logo / QR image), so the built-in
# static view is appropriate. The document root is read per request so it
# always tracks ``settings.MEDIA_ROOT``.
def serve_media(request, path):
    """Serve an uploaded media file from the current ``MEDIA_ROOT``."""
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path(DjangoAdminPath, admin.site.urls),
    path(api_url_path, include((_ninja_patterns, _ninja_app_name), namespace="api")),
    path("", include("allauth.urls")),
    path("accounts/", include("users.urls")),
    # Uploaded media (login branding, ...) — registered BEFORE the SPA catch-all
    # below so a /media/... path is never shadowed by it. The top-level resolver
    # strips the leading slash before matching sub-patterns (its root pattern is
    # "^/"), so the prefix here carries no leading slash (matching the catch-all's
    # "media/" convention) even though ``MEDIA_URL`` itself does.
    re_path(rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$", serve_media),
    # Catch-all for client-side (Vue Router) routes such as /assistant, /admin,
    # /analysis/<id>: serve the SPA shell for any path that no backend route
    # (Django admin, api, allauth, accounts, static/media) has matched yet.
    re_path(
        rf"^(?!{DjangoAdminPath}|api/|accounts/|static/|media/|\.well-known/).*$",
        frontend_index,
        name="frontend-index",
    ),
]
