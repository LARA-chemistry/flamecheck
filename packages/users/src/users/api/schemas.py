"""Ninja schemas for the users API."""

from __future__ import annotations

from typing import Any

from ninja import Schema
from pydantic import BaseModel


class BarcodeScanIn(BaseModel):
    """Payload for the barcode login endpoint."""

    barcode: str
    idempotency_key: str | None = None


class LoginIn(BaseModel):
    """Payload for the username/password login endpoint."""

    username: str
    password: str
    idempotency_key: str | None = None


class RefreshIn(BaseModel):
    """Payload for the token refresh endpoint."""

    refresh: str


class UserOut(BaseModel):
    """
    Minimal public representation of a user.

    ``version`` carries the running FlameCheck version (from
    ``flamecheck.__version__``) so the client can surface it, e.g. in the
    "About" section of the help panels.
    """

    id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    role: str
    lab: str | None = None
    matriculation_no: str | None = None
    labspace_id: str | None = None
    telephone: str | None = None
    course_name: str | None = None
    version: str | None = None
    # Whether the user still needs to complete registration (OAuth students only).
    registered: bool = True

    @classmethod
    def from_user(cls, user: Any) -> UserOut:
        """Build a :class:`UserOut` from a Django user."""
        course = getattr(user, "course", None)
        is_student = user.role == user.Role.STUDENT
        full = user.full_name
        return cls(
            id=user.id,
            username=user.username,
            first_name=user.first_name or None,
            last_name=user.last_name or None,
            full_name=full or None,
            role=user.role,
            lab=user.lab or None,
            matriculation_no=(user.matriculation_no or None) if is_student else None,
            labspace_id=(user.labspace_id or None) if is_student else None,
            telephone=(user.telephone or None) if is_student else None,
            course_name=course.name if course is not None else None,
            version=_flamecheck_version(),
            registered=bool(getattr(user, "registered", True)),
        )


class ProviderOut(BaseModel):
    """A configured OAuth provider (drives one login-page sign-in button)."""

    id: str
    name: str
    login_url: str


class RegistrationConfigOut(BaseModel):
    """Public registration configuration (drives the login-page controls)."""

    registration: str
    providers: list[ProviderOut] = []


class RegisterIn(BaseModel):
    """Payload for the self-registration endpoint (students only)."""

    first_name: str
    last_name: str = ""
    email: str
    password: str
    matriculation_no: str = ""
    lab: str = ""
    telephone: str = ""


class RegisterOut(BaseModel):
    """Acknowledgement for a self-registration request."""

    message: str


class RegistrationIn(BaseModel):
    """Payload for completing registration (course + metadata an OAuth idp lacked)."""

    course_id: int
    first_name: str = ""
    last_name: str = ""
    matriculation_no: str = ""
    labspace_id: str = ""
    lab: str = ""
    telephone: str = ""


class CourseOptionOut(BaseModel):
    """A course offered on the registration page."""

    id: int
    name: str


def _flamecheck_version() -> str:
    """Return the running FlameCheck version, or an empty string if unknown."""
    try:
        import flamecheck

        return flamecheck.__version__ or ""
    except Exception:  # pragma: no cover - defensive; version is best-effort
        return ""


class TokenPairOut(Schema):
    """A short-lived access/refresh token pair."""

    access: str
    refresh: str
    access_expires_in: int
    refresh_expires_in: int
    token_type: str = "Bearer"  # noqa: S105  # standard JWT token-type value


class LoginOut(Schema):
    """Result of a successful login (barcode or password)."""

    tokens: TokenPairOut
    user: UserOut
    analyses: list[Any] = []


class AnalysisSummaryOut(Schema):
    """Compact view of an analysis assigned to the logged-in user."""

    id: int
    type: str
    number: int
    window_status: str
    submission_count: int
    submission_limit: int
    score: int | None = None
