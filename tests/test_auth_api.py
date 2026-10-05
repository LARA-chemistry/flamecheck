"""Tests for the auth endpoints (barcode scan, login, refresh, logout, /me)."""

import pytest
from users import jwt
from users.models import User

pytestmark = pytest.mark.django_db


class TestBarcodeScan:
    def test_unknown_barcode_is_generic_error(self, client):
        resp = client.post("/api/v1/auth/barcode/scan", {"barcode": "FC-999-unknown"}, content_type="application/json")
        assert resp.status_code == 401

    def test_inactive_barcode_rejected(self, client, student, student_barcode):
        student_barcode.active = False
        student_barcode.save()
        resp = client.post(
            "/api/v1/auth/barcode/scan",
            {"barcode": student_barcode.value},
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_valid_barcode_returns_tokens_and_analyses(self, client, student, student_barcode):
        resp = client.post(
            "/api/v1/auth/barcode/scan",
            {"barcode": student_barcode.value},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["username"] == student.username
        assert data["user"]["role"] == User.Role.STUDENT
        assert data["tokens"]["access"]
        assert data["tokens"]["refresh"]
        assert isinstance(data["analyses"], list)


class TestLogin:
    def test_valid_password_login(self, client, student):
        resp = client.post(
            "/api/v1/auth/login",
            {"username": "student1", "password": "testpass123"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["username"] == "student1"

    def test_wrong_password(self, client, student):
        resp = client.post(
            "/api/v1/auth/login",
            {"username": "student1", "password": "wrong"},
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_lockout_after_repeated_failures(self, client, student):
        """After LOGIN_MAX_ATTEMPTS failures the account is locked, even for the right password."""
        from django.conf import settings
        from django.core.cache import cache

        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            resp = client.post(
                "/api/v1/auth/login",
                {"username": "student1", "password": "wrong"},
                content_type="application/json",
            )
            # 401 while the per-IP rate limit still lets attempts through,
            # 400 once it kicks in — either way no login succeeds.
            assert resp.status_code in (400, 401)

        # Drop the per-IP rate-limit counters so the persistent, IP-independent
        # lockout is what answers next.
        cache.clear()
        resp = client.post(
            "/api/v1/auth/login",
            {"username": "student1", "password": "testpass123"},
            content_type="application/json",
        )
        assert resp.status_code == 423

    def test_successful_login_resets_lockout_counter(self, client, student):
        from django.conf import settings
        from django.core.cache import cache

        for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
            client.post(
                "/api/v1/auth/login",
                {"username": "student1", "password": "wrong"},
                content_type="application/json",
            )
        cache.clear()
        # Success clears the failure counter …
        resp = client.post(
            "/api/v1/auth/login",
            {"username": "student1", "password": "testpass123"},
            content_type="application/json",
        )
        assert resp.status_code == 200

        # … so the same number of later failures does not trigger the lockout.
        cache.clear()
        for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
            resp = client.post(
                "/api/v1/auth/login",
                {"username": "student1", "password": "wrong"},
                content_type="application/json",
            )
            assert resp.status_code == 401

    def test_client_ip_uses_last_xff_entry(self):
        """Only the last (proxy-appended) X-Forwarded-For entry is trusted."""
        from users.api.views import _client_ip

        class _Req:
            META = {"HTTP_X_FORWARDED_FOR": "203.0.113.7, 198.51.100.23"}

        assert _client_ip(_Req()) == "198.51.100.23"


class TestTokenLifecycle:
    def test_refresh_rotates_tokens(self, client, student, student_barcode):
        login = client.post(
            "/api/v1/auth/barcode/scan",
            {"barcode": student_barcode.value},
            content_type="application/json",
        ).json()
        refresh = login["tokens"]["refresh"]
        resp = client.post("/api/v1/auth/token/refresh", {"refresh": refresh}, content_type="application/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["access"]
        assert data["refresh"] != refresh

    def test_logout_revokes_tokens(self, client, student, student_barcode, auth_headers):
        login = client.post(
            "/api/v1/auth/barcode/scan",
            {"barcode": student_barcode.value},
            content_type="application/json",
        ).json()
        access = login["tokens"]["access"]

        # authenticated request works
        me = client.get("/api/v1/me", **auth_headers(student))
        assert me.status_code == 200

        # logout bumps token_version
        resp = client.post("/api/v1/auth/logout", **auth_headers(student))
        assert resp.status_code == 200

        student.refresh_from_db()
        assert student.token_version == 1

        # the previously issued token is now revoked
        resp = client.get("/api/v1/me", **auth_headers(student))
        # auth_headers re-mints a *new* token, so test revocation explicitly:
        resp = client.get("/api/v1/me", HTTP_AUTHORIZATION=f"Bearer {access}")
        assert resp.status_code == 401


class TestMe:
    def test_me_requires_auth(self, client):
        assert client.get("/api/v1/me").status_code == 401

    def test_me_returns_profile(self, client, student, auth_headers):
        resp = client.get("/api/v1/me", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == student.username
        assert data["role"] == student.role

    def test_me_includes_course_and_matriculation(self, client, student, auth_headers, course):
        student.course = course
        student.matriculation_no = "12345"
        student.save()
        data = client.get("/api/v1/me", **auth_headers(student)).json()
        assert data["course_name"] == course.name
        assert data["matriculation_no"] == "12345"

    def test_me_course_fields_absent_for_non_student(self, client, admin_user, auth_headers):
        data = client.get("/api/v1/me", **auth_headers(admin_user)).json()
        assert data["course_name"] is None
        assert data["matriculation_no"] is None


class TestJwtUnit:
    def test_issue_and_decode_access(self, student):
        token = jwt.issue_token(student, jwt.ACCESS_TOKEN)
        payload = jwt.decode_token(token, jwt.ACCESS_TOKEN)
        assert payload["sub"] == str(student.id)
        assert payload["type"] == "access"

    def test_wrong_type_rejected(self, student):
        token = jwt.issue_token(student, jwt.REFRESH_TOKEN)
        with pytest.raises(jwt.TokenError):
            jwt.decode_token(token, jwt.ACCESS_TOKEN)

    def test_tampered_token_rejected(self, student):
        token = jwt.issue_token(student, jwt.ACCESS_TOKEN)
        with pytest.raises(jwt.TokenError):
            jwt.decode_token(token + "x", jwt.ACCESS_TOKEN)
