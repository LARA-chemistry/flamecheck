"""
Ninja API views for onboarding (self-registration, e-mail confirmation, OAuth).

Endpoints:

* ``GET  /onboarding/config``        — public; which onboarding mode is active
  and which OAuth providers are offered (drives the login page).
* ``POST /auth/register``            — public; create a student account pending
  e-mail confirmation (self-registration mode only).
* ``POST /auth/oauth/exchange``      — exchange the allauth session (created by
  an OAuth sign-in) for a JWT pair (the SPA is JWT-based, not session-based).
* ``GET  /onboarding/courses``       — active courses for the onboarding page.
* ``POST /onboarding/complete``      — enrol the (OAuth) student in a course,
  fill missing metadata (random labspace if absent) and generate their analyses.

The e-mail-confirmation *link* itself is a plain Django view
(:func:`users.views.verify_email`) so it can be opened from the e-mail without
any token in the URL query string.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.core.mail import send_mail
from django.urls import reverse
from ninja import Router
from ninja.errors import AuthenticationError, HttpError, ValidationError
from users import email_verification
from users.api.schemas import (
    CourseOptionOut,
    OnboardingConfigOut,
    OnboardingIn,
    RegisterIn,
    RegisterOut,
    UserOut,
)
from users.models import User, generate_labspace_id

logger = logging.getLogger("flamecheck.audit")

router = Router(tags=["onboarding"])

UserModel = get_user_model()


def _onboarding_mode() -> str:
    """Return the active onboarding mode (from the settings singleton)."""
    from config.models import AppSettings

    return AppSettings.get_onboarding_mode()


def _configured_providers() -> list[str]:
    """The ids of the OAuth providers configured for this deployment."""
    providers = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}) or {}
    return list(providers.keys())


def _derive_username(email: str) -> str:
    """Derive a unique, valid username from the local part of an e-mail address."""
    base = email.split("@", 1)[0].lower()
    base = re.sub(r"[^a-z0-9._-]", "", base)[:30] or "student"
    candidate = base
    suffix = 2
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base[:29]}-{suffix}"
        suffix += 1
    return candidate


def _send_verification_email(request: Any, user: User) -> None:
    """Send the e-mail-confirmation link for ``user`` (console backend in dev)."""
    token = email_verification.make_verification_token(user.username)
    url = request.build_absolute_uri(reverse("users:verify-email", kwargs={"token": token}))
    prefix = getattr(settings, "EMAIL_SUBJECT_PREFIX", "")
    subject = f"{prefix}Confirm your FlameCheck account"
    message = (
        f"Hi {user.name or user.username},\n\n"
        "your FlameCheck student account has been created. Please confirm your "
        "e-mail address by opening the link below (it stays valid for 48 hours):\n\n"
        f"{url}\n\n"
        "If you did not register for FlameCheck, you can ignore this e-mail.\n"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


@router.get("/onboarding/config", response=OnboardingConfigOut, auth=None)
def onboarding_config(request):
    """Public onboarding configuration (active mode + available OAuth providers)."""
    return {"onboarding": _onboarding_mode(), "providers": _configured_providers()}


@router.post("/auth/register", response={202: RegisterOut}, auth=None)
def register(request, payload: RegisterIn):
    """
    Create a student account pending e-mail confirmation (self-registration only).

    The account is inactive until the confirmation link in the e-mail is opened.
    Registration is only possible while the onboarding mode is
    ``self_registration``; it always creates a *student*.
    """
    if _onboarding_mode() != "self_registration":
        raise HttpError(403, "Registration is not available. Accounts are managed by your instructor.")

    email = payload.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValidationError({"email": ["Enter a valid e-mail address."]})
    if User.objects.filter(email__iexact=email).exists():
        raise HttpError(409, "An account with this e-mail address already exists.")
    if not payload.name.strip():
        raise ValidationError({"name": ["Name is required."]})

    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        validate_password(payload.password)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from exc

    user = User.objects.create_user(
        username=_derive_username(email),
        email=email,
        password=payload.password,
        name=payload.name.strip(),
        role=User.Role.STUDENT,
        matriculation_no=payload.matriculation_no.strip(),
        lab=payload.lab.strip(),
        telephone=payload.telephone.strip(),
        is_active=False,  # activated by the e-mail confirmation link
    )
    logger.info("Self-registration: pending account %s created (email %s)", user.username, email)
    _send_verification_email(request, user)
    return 202, {"message": f"Registration received. Please confirm your e-mail address at {email}."}


@router.post("/auth/oauth/exchange", auth=None)
def oauth_exchange(request):
    """
    Exchange an allauth session (from an OAuth sign-in) for a JWT pair.

    The SPA is JWT-based, so after the browser is redirected back from the
    identity provider (with a Django session set by allauth) this endpoint mints
    the access/refresh tokens the SPA stores, then clears the session.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "No active sign-in session to exchange.")
    from users.api.views import _login_out

    out = _login_out(user, request)
    logger.info("OAuth exchange: %s (%s) obtained a JWT pair", user.username, user.role)
    logout(request)  # the SPA now relies on the JWT, not the session
    return out


@router.get("/onboarding/courses", response=list[CourseOptionOut])
def onboarding_courses(request):
    """List the active courses a (student) may pick on the onboarding page."""
    user = request.user
    if not getattr(user, "is_student", False):
        raise HttpError(403, "Only students can view onboarding courses.")
    from config.models import Course

    courses = Course.objects.filter(is_active=True).order_by("name")
    return [{"id": c.id, "name": c.name} for c in courses]


@router.post("/onboarding/complete", response=UserOut)
def onboarding_complete(request, payload: OnboardingIn):
    """
    Complete onboarding for an (OAuth) student.

    Enrols the student in the chosen course, fills in metadata the identity
    provider did not supply (a random labspace id when none is provided), marks
    the student onboarded and generates the course's analyses for them.
    """
    user = request.user
    if not getattr(user, "is_student", False):
        raise HttpError(403, "Only students can complete onboarding.")
    if getattr(user, "onboarded", True):
        raise HttpError(409, "Onboarding was already completed for this account.")

    from config.models import Course

    course = Course.objects.filter(id=payload.course_id, is_active=True).first()
    if course is None:
        raise HttpError(404, "Course not found (or inactive).")

    # Preserve values the identity provider already supplied; only override with
    # non-empty onboarding input. The labspace is always set (provided or random).
    if payload.name.strip():
        user.name = payload.name.strip()
    if payload.matriculation_no.strip():
        user.matriculation_no = payload.matriculation_no.strip()
    if payload.lab.strip():
        user.lab = payload.lab.strip()
    if payload.telephone.strip():
        user.telephone = payload.telephone.strip()
    user.labspace_id = payload.labspace_id.strip() or generate_labspace_id()
    user.course = course
    user.role = User.Role.STUDENT
    user.onboarded = True
    user.is_active = True
    user.save()

    from analyses.services.onboarding import NoAnalysisTypeError, generate_course_analyses

    try:
        instances = generate_course_analyses(user, course)
    except NoAnalysisTypeError as exc:
        logger.error("Onboarding for %s: could not generate analyses (%s)", user.username, exc)
        raise HttpError(400, "No analysis types are available to generate analyses yet.") from exc
    logger.info(
        "Onboarding complete: %s enrolled in %s (%d analyses generated)",
        user.username,
        course.name,
        len(instances),
    )
    return UserOut.from_user(user)
