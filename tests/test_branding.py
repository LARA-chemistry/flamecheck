"""Tests for login-page branding (logo / QR upload) and media serving."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest
from config.models import AppSettings
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def _png(tag: str) -> bytes:
    """A tiny stand-in image payload (content is not validated by the API)."""
    return f"fake-png-{tag}".encode()


def _version(url: str | None) -> str:
    """The ``?v=`` cache-buster value of a media URL (empty when absent)."""
    if url and "?v=" in url:
        return url.rsplit("?", 1)[1]
    return ""


@pytest.fixture(scope="module", autouse=True)
def branding_media_root(tmp_path_factory):
    """
    Point ``MEDIA_ROOT`` at one stable throwaway dir for the whole module.

    ``FileSystemStorage.base_location`` is a ``cached_property`` on the shared
    default storage, so the media root must not change between tests; a per-test
    dir would be cached on the first write and then mismatch later tests. The
    live settings object is mutated directly (the function-scoped ``settings``
    fixture cannot be requested from a module-scoped one).
    """
    original = settings.MEDIA_ROOT
    media = tmp_path_factory.mktemp("branding-media")
    settings.MEDIA_ROOT = str(media)
    yield media
    settings.MEDIA_ROOT = original


@pytest.fixture(autouse=True)
def clean_branding(branding_media_root):
    """
    Remove branding files left by a previous test in the shared media dir.

    The test DB is rolled back per test, but the module-wide media dir persists;
    a stale ``branding/<file>`` would otherwise make ``get_available_name()``
    suffix the next upload instead of overwriting the stable path.
    """
    branding = Path(branding_media_root) / "branding"
    if branding.exists():
        shutil.rmtree(branding)
    yield


class TestBrandingPublic:
    def test_no_branding_configured(self, client):
        resp = client.get("/api/v1/branding")
        assert resp.status_code == 200
        assert resp.json() == {"login_logo": None, "login_qr": None}


class TestBrandingUpload:
    def test_upload_requires_admin(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/admin/branding/logo",
            {"file": SimpleUploadedFile("logo.png", _png("x"), content_type="image/png")},
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_bad_extension_rejected(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/branding/logo",
            {"file": SimpleUploadedFile("logo.exe", b"MZ", content_type="application/octet-stream")},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 400
        assert not AppSettings.get_instance().login_logo.name

    def test_upload_returns_cache_busted_url(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/branding/logo",
            {"file": SimpleUploadedFile("logo.png", _png("1"), content_type="image/png")},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        url = resp.json()["login_logo"]
        # Clean path (no doubled "branding/branding/") plus a cache-buster.
        assert url.startswith("/media/branding/login_logo.png?v=")
        assert re.fullmatch(r"v=\d+", _version(url)) is not None

    def test_reupload_changes_version(self, client, admin_user, auth_headers):
        def upload() -> str:
            r = client.post(
                "/api/v1/admin/branding/logo",
                {"file": SimpleUploadedFile("logo.png", _png("n"), content_type="image/png")},
                **auth_headers(admin_user),
            )
            return r.json()["login_logo"]

        first = upload()
        second = upload()  # re-upload to the same stable path

        assert _version(first) and _version(second)
        # The base path (without the cache-buster) stays stable across uploads.
        assert first.split("?", 1)[0] == second.split("?", 1)[0] == "/media/branding/login_logo.png"

        # The cache-buster is the file's mtime in ms, so it must change when the
        # file is rewritten. Bump the mtime explicitly (a filesystem's mtime
        # granularity can be coarser than two fast writes) and confirm the
        # version tracks it — this is what forces the browser to refresh.
        logo = AppSettings.get_instance().login_logo
        st = os.stat(logo.path)
        newer = st.st_mtime_ns + 5_000_000_000  # +5s
        os.utime(logo.path, ns=(newer, newer))
        bumped = client.get("/api/v1/branding").json()["login_logo"]

        assert bumped.split("?", 1)[0] == "/media/branding/login_logo.png"
        assert bumped != second, "a changed mtime must change the cache-buster"

    def test_remove_logo(self, client, admin_user, auth_headers):
        client.post(
            "/api/v1/admin/branding/logo",
            {"file": SimpleUploadedFile("logo.png", _png("1"), content_type="image/png")},
            **auth_headers(admin_user),
        )
        resp = client.delete("/api/v1/admin/branding/logo", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["login_logo"] is None
        assert not AppSettings.get_instance().login_logo.name


class TestMediaServing:
    def test_media_served_with_debug_off(self, client, admin_user, auth_headers, settings):
        # The media route must work even when DEBUG is off (production/Docker),
        # because the production stack has no reverse proxy in front of Django.
        settings.DEBUG = False
        resp = client.post(
            "/api/v1/admin/branding/qr",
            {"file": SimpleUploadedFile("qr.png", _png("qr"), content_type="image/png")},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        url = AppSettings.get_instance().login_qr.url
        # Request the media file directly (strip the client-side cache buster).
        media_path = url.split("?", 1)[0]
        got = client.get(media_path)
        assert got.status_code == 200
        # The media view returns a streaming ``FileResponse``; read its body.
        body = b"".join(got.streaming_content)
        assert _png("qr") in body
