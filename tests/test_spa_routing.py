"""
Tests for the SPA catch-all URL routing.

The Vue app uses client-side routing, so any non-backend path (e.g. ``/assistant``,
``/analysis/123``) must be answered with the built SPA shell instead of a 404,
while backend routes (admin, api, accounts) keep their own handlers.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestSpaCatchAll:
    def test_client_routes_serve_spa_shell(self, client):
        # /admin is the SPA admin panel route (the Django admin moved to /admin-django/).
        for route in ["/", "/assistant", "/admin", "/analysis/123", "/login"]:
            resp = client.get(route)
            assert resp.status_code == 200, f"{route} should serve the SPA shell"
            body = resp.content.decode()
            # The built Vue app mounts into a #app element.
            assert 'id="app"' in body

    def test_django_admin_not_swallowed(self, client):
        # /admin-django/ is the Django admin (a redirect to its login), not the SPA.
        resp = client.get("/admin-django/")
        assert resp.status_code == 302
        assert "admin-django/login" in resp["Location"]

    def test_api_not_swallowed(self, client):
        # An unauthenticated API call is a 401, proving the catch-all didn't
        # intercept /api/... paths.
        resp = client.get("/api/v1/me")
        assert resp.status_code == 401

    def test_frontend_index_reversible(self):
        # The catch-all route must be reversible (resolves to a concrete path).
        assert reverse("frontend-index") in ("", "/")
