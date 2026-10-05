"""Ninja API views for auth (barcode, password, refresh, logout) and ``/me``."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.utils import timezone
from ninja import Router
from ninja.errors import AuthenticationError, HttpError, ValidationError
from users import jwt
from users.api.schemas import (
    BarcodeScanIn,
    LoginIn,
    LoginOut,
    RefreshIn,
    TokenPairOut,
    UserOut,
)
from users.models import LoginAttempt, StudentBarcode, User

logger = logging.getLogger("flamecheck.audit")

router = Router(tags=["auth"])

# Rate limits via the (shared) Django cache: max attempts per window per key.
_SCAN_RATE_LIMIT = 10
_SCAN_WINDOW_SECONDS = 60
_LOGIN_RATE_LIMIT = 5
_LOGIN_WINDOW_SECONDS = 60

# Persistent lockout per username: after ``LOGIN_MAX_ATTEMPTS`` consecutive
# failures the account refuses logins for ``LOGIN_LOCKOUT_SECONDS``, regardless
# of the client IP (which is attacker-controllable). A successful login resets
# the counter; failures older than the lockout window stop counting.


def _client_ip(request) -> str | None:
    """
    Best-effort extraction of the client IP address.

    Behind a reverse proxy the ``X-Forwarded-For`` chain starts with
    client-supplied (forgeable) entries and ends with the real peer address
    appended by the closest trusted proxy — only that last entry is trusted,
    so a forged first entry cannot be used to bypass the rate limits.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip() or None
    return request.META.get("REMOTE_ADDR")


def _rate_limited(key: str, limit: int, window: int) -> bool:
    """Return True if the key has been seen ``limit`` times within ``window`` seconds."""
    bucket = cache.get(f"rl:{key}", 0)
    if bucket >= limit:
        return True
    cache.set(f"rl:{key}", bucket + 1, window)
    return False


def _summary_for(user: User) -> list[dict]:
    """Build the compact analysis list shown right after login."""
    from analyses.api.schemas import AnalysisSummary
    from analyses.models import AnalysisInstance

    instances = AnalysisInstance.objects.for_student(user)
    return [AnalysisSummary.from_instance(i) for i in instances]


def _login_out(user: User, request) -> dict:
    """Assemble the full login response payload."""
    return {
        "tokens": jwt.token_pair(user),
        "user": UserOut.from_user(user),
        "analyses": _summary_for(user),
    }


def _record_attempt(username: str, ip: str | None, success: bool) -> None:
    """Persist a login attempt for audit/lockout purposes."""
    LoginAttempt.objects.create(username=username, ip_address=ip, success=success)


def _locked_out(username: str) -> bool:
    """
    True if ``username`` is currently locked out after too many failures.

    Failures count since the most recent successful login (a stored success
    resets the counter) and only within the lockout window. The count is
    IP-independent: an attacker must not be able to keep an account unlocked
    by rotating source addresses.
    """
    failures = LoginAttempt.objects.filter(username=username, success=False)
    last_success = (
        LoginAttempt.objects.filter(username=username, success=True)
        .order_by("-attempted_at")
        .values_list("attempted_at", flat=True)
        .first()
    )
    if last_success is not None:
        failures = failures.filter(attempted_at__gt=last_success)
    window = timedelta(seconds=settings.LOGIN_LOCKOUT_SECONDS)
    return failures.filter(attempted_at__gte=timezone.now() - window).count() >= settings.LOGIN_MAX_ATTEMPTS


@router.post("/auth/barcode/scan", response=LoginOut, auth=None)
def barcode_scan(request, payload: BarcodeScanIn):
    """
    Validate a student barcode and return tokens plus assigned analyses.

    The lookup is performed server-side. An unknown or inactive barcode raises
    a generic authentication error so attackers cannot probe which barcodes
    exist.
    """
    ip = _client_ip(request)
    if _rate_limited(f"scan:{ip}", _SCAN_RATE_LIMIT, _SCAN_WINDOW_SECONDS):
        raise ValidationError({"barcode": ["Too many requests. Try again later."]})

    value = payload.barcode.strip()
    barcode = StudentBarcode.objects.filter(value=value, active=True).select_related("student").first()
    if barcode is None:
        logger.info("Barcode scan: unknown or inactive barcode from %s", ip)
        raise AuthenticationError(401, "Invalid or inactive barcode.")
    user = barcode.student
    if not user.is_active:
        raise AuthenticationError(403, "Account is disabled.")
    user.token_version = int(getattr(user, "token_version", 0) or 0)  # ensure field is loaded
    logger.info("Barcode scan: student %s logged in", user.username)
    return _login_out(user, request)


@router.post("/auth/login", response=LoginOut, auth=None)
def login(request, payload: LoginIn):
    """Username/password login for all roles (students, assistants, admins)."""
    ip = _client_ip(request)
    key = f"login:{payload.username}:{ip or 'no-ip'}"
    if _rate_limited(key, _LOGIN_RATE_LIMIT, _LOGIN_WINDOW_SECONDS):
        # Note: the limiter counts every attempt (successful ones included),
        # so the message must not imply the password is wrong.
        message = f"Too many login attempts (max {_LOGIN_RATE_LIMIT} per minute). Try again in a minute."
        raise ValidationError({"username": [message]})

    # Persistent, IP-independent lockout (the rate limit above is per IP and
    # therefore bypassable; this one is not).
    if _locked_out(payload.username):
        raise HttpError(423, "Too many failed login attempts. Try again in a few minutes.")

    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        _record_attempt(payload.username, ip, success=False)
        raise AuthenticationError(401, "Invalid username or password.")
    if not user.is_active:
        raise AuthenticationError(403, "Account is disabled.")
    _record_attempt(payload.username, ip, success=True)
    logger.info("Password login: %s (%s) logged in", user.username, user.role)
    return _login_out(user, request)


@router.post("/auth/token/refresh", response=TokenPairOut, auth=None)
def token_refresh(request, payload: RefreshIn):
    """Rotate a refresh token into a fresh access/refresh pair."""
    payload_ = jwt.validate_refresh_token(payload.refresh)
    user = User.objects.filter(pk=int(payload_["sub"]), is_active=True).first()
    if user is None:
        raise AuthenticationError(401, "User not found or disabled.")
    return jwt.refresh_pair(payload.refresh, user)


@router.post("/auth/logout", response=None)
def logout(request):
    """Revoke all JWTs issued to the current user."""
    user = request.user
    if user.is_authenticated and hasattr(user, "token_version"):
        user.token_version = int(user.token_version) + 1
        user.save(update_fields=["token_version"])
        logger.info("Logout: %s revoked tokens", user.username)


@router.get("/me", response=UserOut)
def me(request):
    """Return the current user's minimal profile data."""
    return UserOut.from_user(request.user)
