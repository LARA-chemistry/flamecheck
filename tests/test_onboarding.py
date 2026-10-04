"""Tests for the onboarding feature (manual / self-registration / OAuth)."""

from __future__ import annotations

import pytest
from analyses.factory import AnalysisTypeFactory
from analyses.models import AnalysisInstance
from analyses.services.onboarding import NoAnalysisTypeError, generate_course_analyses
from config.factory import AppSettingsFactory, CourseFactory
from django.core import mail, signing
from substances.factory import create_ion_catalog
from users import email_verification, jwt
from users.factory import UserFactory
from users.models import User

pytestmark = pytest.mark.django_db


def _set_onboarding(mode: str):
    """Set the active onboarding mode on the singleton (updates, not just creates)."""
    from config.models import AppSettings

    s = AppSettings.get_instance()
    s.onboarding = mode
    s.save()
    return s


# A realistic SOCIALACCOUNT_PROVIDERS value for a Keycloak realm, used to verify
# the OpenID Connect provider is exposed to the login page and resolvable.
# ``APPS`` is a list of app-config dicts (one per realm).
_KEYCLOAK_PROVIDERS = {
    "openid_connect": {
        "APPS": [
            {
                "provider_id": "keycloak",
                "name": "Keycloak",
                "client_id": "flamecheck",
                "secret": "s3cret",
                "settings": {"server_url": "https://keycloak.example.com/realms/flamecheck"},
            }
        ]
    }
}


# --------------------------------------------------------------------------- #
# Models / helpers                                                            #
# --------------------------------------------------------------------------- #
class TestOnboardingModels:
    def test_appsettings_onboarding_defaults_manual(self, db):
        s = AppSettingsFactory()
        assert s.onboarding == "manual"

    def test_get_onboarding_mode_no_row(self, db):
        from config.models import AppSettings

        assert AppSettings.get_onboarding_mode() == "manual"

    def test_get_onboarding_mode_reads_row(self, db):
        from config.models import AppSettings

        AppSettingsFactory(onboarding="oauth")
        assert AppSettings.get_onboarding_mode() == "oauth"

    def test_user_onboarded_defaults_true(self, db):
        u = UserFactory()
        assert u.onboarded is True


class TestEmailVerificationTokens:
    def test_roundtrip(self):
        token = email_verification.make_verification_token("someone")
        assert email_verification.verify_token(token, max_age=3600) == "someone"

    def test_bad_signature(self):
        with pytest.raises(signing.BadSignature):
            email_verification.verify_token("garbage-token", max_age=3600)

    def test_expired(self):
        token = email_verification.make_verification_token("someone")
        # A token older than max_age raises SignatureExpired.
        with pytest.raises(signing.SignatureExpired):
            email_verification.verify_token(token, max_age=-1)

    def test_generate_labspace_id_format(self):
        from users.models import generate_labspace_id

        value = generate_labspace_id()
        assert value.startswith("LS-")
        assert len(value) == len("LS-") + 8


# --------------------------------------------------------------------------- #
# Public onboarding config                                                    #
# --------------------------------------------------------------------------- #
class TestOnboardingConfigEndpoint:
    def test_returns_mode_and_providers(self, client, settings):
        AppSettingsFactory(onboarding="self_registration")
        settings.SOCIALACCOUNT_PROVIDERS = {"google": {}}
        resp = client.get("/api/v1/onboarding/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["onboarding"] == "self_registration"
        # Each provider is an entry with a display name + allauth login URL.
        assert data["providers"] == [
            {"id": "google", "name": "google", "login_url": "/google/login/"},
        ]

    def test_default_manual_no_providers(self, client):
        resp = client.get("/api/v1/onboarding/config")
        assert resp.status_code == 200
        assert resp.json()["onboarding"] == "manual"
        assert resp.json()["providers"] == []

    def test_keycloak_provider_exposed(self, client, settings):
        """A configured Keycloak (OIDC) realm is offered with its login URL."""
        settings.SOCIALACCOUNT_PROVIDERS = _KEYCLOAK_PROVIDERS
        resp = client.get("/api/v1/onboarding/config")
        assert resp.status_code == 200
        assert resp.json()["providers"] == [
            {"id": "keycloak", "name": "Keycloak", "login_url": "/oidc/keycloak/login/"},
        ]


class TestConfiguredProviders:
    """How SOCIALACCOUNT_PROVIDERS maps to the login entries the page offers."""

    def test_keycloak_entry(self, settings):
        from users.api.onboarding import _configured_providers

        settings.SOCIALACCOUNT_PROVIDERS = _KEYCLOAK_PROVIDERS
        assert _configured_providers() == [
            {"id": "keycloak", "name": "Keycloak", "login_url": "/oidc/keycloak/login/"},
        ]

    def test_oidc_without_apps_exposes_nothing(self, settings):
        from users.api.onboarding import _configured_providers

        settings.SOCIALACCOUNT_PROVIDERS = {"openid_connect": {"APPS": {}}}
        assert _configured_providers() == []

    def test_mixed_standard_and_oidc(self, settings):
        from users.api.onboarding import _configured_providers

        settings.SOCIALACCOUNT_PROVIDERS = {"google": {}, **_KEYCLOAK_PROVIDERS}
        assert _configured_providers() == [
            {"id": "google", "name": "google", "login_url": "/google/login/"},
            {"id": "keycloak", "name": "Keycloak", "login_url": "/oidc/keycloak/login/"},
        ]

    def test_allauth_resolves_keycloak_app(self, settings, rf):
        """The env-var config must resolve to a SocialApp allauth can actually use."""
        from allauth.socialaccount.adapter import get_adapter

        settings.SOCIALACCOUNT_PROVIDERS = _KEYCLOAK_PROVIDERS
        app = get_adapter().get_app(rf.get("/"), provider="keycloak")
        assert app.provider == "openid_connect"
        assert app.provider_id == "keycloak"
        assert app.client_id == "flamecheck"
        assert app.settings["server_url"].endswith("/realms/flamecheck")


# --------------------------------------------------------------------------- #
# Self-registration                                                           #
# --------------------------------------------------------------------------- #
_REGISTER = {
    "first_name": "New",
    "last_name": "Student",
    "email": "new.student@example.com",
    "password": "Str0ngPass!234",
}


class TestSelfRegistration:
    def _register(self, client, **overrides):
        payload = {**_REGISTER, **overrides}
        return client.post("/api/v1/auth/register", payload, content_type="application/json")

    def test_forbidden_when_mode_not_self_registration(self, client):
        AppSettingsFactory(onboarding="manual")
        resp = self._register(client)
        assert resp.status_code == 403

    def test_creates_inactive_student_and_sends_email(self, client):
        AppSettingsFactory(onboarding="self_registration")
        mail.outbox = []
        resp = self._register(client)
        assert resp.status_code == 202
        assert "confirm" in resp.json()["message"]

        user = User.objects.get(email="new.student@example.com")
        assert user.role == User.Role.STUDENT
        assert user.is_active is False
        assert user.onboarded is True
        assert user.username  # derived from the e-mail local part
        assert user.check_password("Str0ngPass!234")

        assert len(mail.outbox) == 1
        body = mail.outbox[0].message().as_string()
        assert "new.student@example.com" in mail.outbox[0].to
        assert "/accounts/verify-email/" in body

    def test_duplicate_email_409(self, client):
        AppSettingsFactory(onboarding="self_registration")
        UserFactory(email="new.student@example.com")
        assert self._register(client).status_code == 409

    def test_weak_password_rejected(self, client):
        AppSettingsFactory(onboarding="self_registration")
        assert self._register(client, password="short").status_code == 422

    def test_invalid_email_rejected(self, client):
        AppSettingsFactory(onboarding="self_registration")
        assert self._register(client, email="not-an-email").status_code == 422

    def test_missing_name_rejected(self, client):
        AppSettingsFactory(onboarding="self_registration")
        assert self._register(client, first_name="   ", last_name="   ").status_code == 422

    def test_verify_email_activates_account(self, client):
        AppSettingsFactory(onboarding="self_registration")
        self._register(client)
        user = User.objects.get(email="new.student@example.com")
        token = email_verification.make_verification_token(user.username)

        resp = client.get(f"/accounts/verify-email/{token}/")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/login?confirmed=1"
        user.refresh_from_db()
        assert user.is_active is True
        assert user.onboarded is True

    def test_verify_email_invalid_token(self, client):
        AppSettingsFactory(onboarding="self_registration")
        self._register(client)
        user = User.objects.get(email="new.student@example.com")
        resp = client.get("/accounts/verify-email/not-a-real-token/")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/login?confirm_error=invalid"
        user.refresh_from_db()
        assert user.is_active is False

    def test_login_works_after_confirmation(self, client):
        AppSettingsFactory(onboarding="self_registration")
        self._register(client)
        user = User.objects.get(email="new.student@example.com")
        token = email_verification.make_verification_token(user.username)
        client.get(f"/accounts/verify-email/{token}/")

        resp = client.post(
            "/api/v1/auth/login",
            {"username": user.username, "password": "Str0ngPass!234"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["username"] == user.username

    def test_inactive_user_cannot_login_before_confirm(self, client):
        AppSettingsFactory(onboarding="self_registration")
        self._register(client)
        user = User.objects.get(email="new.student@example.com")
        resp = client.post(
            "/api/v1/auth/login",
            {"username": user.username, "password": "Str0ngPass!234"},
            content_type="application/json",
        )
        # An inactive account fails authentication outright (401), not 403.
        assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# OAuth adapter                                                               #
# --------------------------------------------------------------------------- #
class TestOAuthAdapter:
    def _adapter(self):
        from users.adapters import SocialAccountAdapter

        return SocialAccountAdapter()

    def test_is_open_for_signup_by_mode(self, db, rf):
        adapter = self._adapter()
        _set_onboarding("oauth")
        assert adapter.is_open_for_signup(rf.get("/"), object()) is True
        _set_onboarding("manual")
        assert adapter.is_open_for_signup(rf.get("/"), object()) is False

    def test_populate_user_sets_student_and_unonboarded(self, db, rf):
        adapter = self._adapter()
        # A fresh account with no name yet (as allauth would create it), so the
        # adapter's name-population branch runs.
        base_user = UserFactory(first_name="", last_name="")

        class _FakeSocialLogin:
            user = base_user

        user = adapter.populate_user(rf.get("/"), _FakeSocialLogin(), {"name": "OAuth Kid"})
        assert user is base_user
        assert user.role == User.Role.STUDENT
        assert user.onboarded is False
        assert user.first_name == "OAuth"
        assert user.last_name == "Kid"


# --------------------------------------------------------------------------- #
# OAuth session -> JWT exchange                                               #
# --------------------------------------------------------------------------- #
class TestOauthExchange:
    def test_no_session_401(self, client):
        resp = client.post("/api/v1/auth/oauth/exchange", {}, content_type="application/json")
        assert resp.status_code == 401

    def test_session_user_gets_jwt(self, client, student):
        client.force_login(student)
        resp = client.post("/api/v1/auth/oauth/exchange", {}, content_type="application/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["username"] == student.username
        assert data["tokens"]["access"]
        assert data["tokens"]["refresh"]
        # The session is cleared after the exchange (the SPA now uses the JWT).
        resp2 = client.post("/api/v1/auth/oauth/exchange", {}, content_type="application/json")
        assert resp2.status_code == 401


# --------------------------------------------------------------------------- #
# Onboarding courses + completion                                             #
# --------------------------------------------------------------------------- #
def _make_types(db):
    """Two analysis types sharing a 6-ion possible set (enough to randomize)."""
    ions = create_ion_catalog(["sodium", "potassium", "ammonium", "magnesium", "calcium", "chloride"])
    t1 = AnalysisTypeFactory(name="Type A", possible_ions=ions)
    t2 = AnalysisTypeFactory(name="Type B", possible_ions=ions)
    return t1, t2, ions


class TestOnboardingCourses:
    def test_student_sees_active_courses(self, client, student, course):
        CourseFactory(name="Second Course", is_active=True)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {jwt.issue_token(student, jwt.ACCESS_TOKEN)}"}
        resp = client.get("/api/v1/onboarding/courses", **headers)
        assert resp.status_code == 200
        names = {c["name"] for c in resp.json()}
        assert course.name in names and "Second Course" in names

    def test_non_student_forbidden(self, client, assistant):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {jwt.issue_token(assistant, jwt.ACCESS_TOKEN)}"}
        assert client.get("/api/v1/onboarding/courses", **headers).status_code == 403


class TestOnboardingComplete:
    def _headers(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {jwt.issue_token(user, jwt.ACCESS_TOKEN)}"}

    def _complete(self, client, student, course, **overrides):
        payload = {"course_id": course.id, **overrides}
        return client.post(
            "/api/v1/onboarding/complete", payload, content_type="application/json", **self._headers(student)
        )

    def test_non_student_forbidden(self, client, assistant, course):
        payload = {"course_id": course.id}
        resp = client.post(
            "/api/v1/onboarding/complete", payload, content_type="application/json", **self._headers(assistant)
        )
        assert resp.status_code == 403

    def test_already_onboarded_409(self, client, student, course):
        student.onboarded = True
        student.save()
        assert self._complete(client, student, course).status_code == 409

    def test_unknown_course_404(self, client, student, course):
        student.onboarded = False
        student.save()
        assert self._complete(client, student, course=course, course_id=99999).status_code == 404

    def test_enrolls_generates_analyses_and_random_labspace(self, client, student, course, db):
        _, _, ions = _make_types(db)
        AppSettingsFactory(analyses_per_course=3)
        student.onboarded = False
        student.labspace_id = ""  # the fixture sets one; clear it to test generation
        student.save()

        resp = self._complete(client, student, course, first_name="OAuth", last_name="Kid", matriculation_no="M999")
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.course_id == course.id
        assert student.onboarded is True
        assert student.is_active is True
        assert student.full_name == "OAuth Kid"
        assert student.matriculation_no == "M999"
        assert student.labspace_id.startswith("LS-")  # randomly generated

        # One instance per announcement (1..3), each assigned to the student.
        instances = AnalysisInstance.objects.for_student(student)
        assert {i.number for i in instances} == {1, 2, 3}
        assert all(i.course_id == course.id for i in instances)
        possible_ids = {ion.id for ion in ions}
        # Each instance has a randomized non-empty composition within the possible set.
        for i in instances:
            correct_ids = set(i.correct_ions.values_list("id", flat=True))
            assert 1 <= len(correct_ids) <= 5
            assert correct_ids <= possible_ids
            assert i.assignments.filter(student=student).exists()

    def test_provided_labspace_preserved(self, client, student, course, db):
        _make_types(db)
        AppSettingsFactory(analyses_per_course=1)
        student.onboarded = False
        student.save()
        resp = self._complete(client, student, course, labspace_id="LS-PROVIDED1")
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.labspace_id == "LS-PROVIDED1"

    def test_empty_metadata_preserves_oauth_values(self, client, student, course, db):
        _make_types(db)
        AppSettingsFactory(analyses_per_course=1)
        student.onboarded = False
        student.first_name = "From"
        student.last_name = "OAuth"
        student.save()
        resp = self._complete(client, student, course)  # no name supplied
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.full_name == "From OAuth"  # not blanked

    def test_no_types_returns_400(self, client, student, course, db):
        AppSettingsFactory(analyses_per_course=1)
        student.onboarded = False
        student.save()
        assert self._complete(client, student, course).status_code == 400


# --------------------------------------------------------------------------- #
# generate_course_analyses service                                            #
# --------------------------------------------------------------------------- #
class TestGenerateCourseAnalyses:
    def test_creates_n_instances_with_assignments(self, db, student, course):
        _make_types(db)
        import random

        created = generate_course_analyses(student, course, analyses_count=2, rng=random.Random(42))
        assert len(created) == 2
        assert [i.number for i in created] == [1, 2]
        for i in created:
            assert i.course_id == course.id
            assert i.correct_ions.count() >= 1
            assert i.window_status() in ("open", "submitted")

    def test_zero_count_creates_nothing(self, db, student, course):
        _make_types(db)
        assert generate_course_analyses(student, course, analyses_count=0) == []

    def test_idempotent_per_number(self, db, student, course):
        _make_types(db)
        generate_course_analyses(student, course, analyses_count=2)
        second = generate_course_analyses(student, course, analyses_count=2)
        assert second == []  # numbers 1..2 already assigned -> skipped
        assert AnalysisInstance.objects.for_student(student).count() == 2

    def test_defaults_to_analyses_per_course(self, db, student, course):
        _make_types(db)
        AppSettingsFactory(analyses_per_course=4)
        created = generate_course_analyses(student, course)
        assert len(created) == 4

    def test_no_types_raises(self, db, student, course):
        with pytest.raises(NoAnalysisTypeError):
            generate_course_analyses(student, course, analyses_count=1)

    def test_random_composition_varies(self, db, student, course):
        _make_types(db)
        created = generate_course_analyses(student, course, analyses_count=1)
        ids = set(created[0].correct_ions.values_list("id", flat=True))
        # The subset is non-empty and bounded.
        assert 1 <= len(ids) <= 5
