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
    """Minimal public representation of a user."""

    id: int
    username: str
    name: str | None
    role: str
    lab: str | None = None
    matriculation_no: str | None = None
    course_name: str | None = None

    @classmethod
    def from_user(cls, user: Any) -> UserOut:
        """Build a :class:`UserOut` from a Django user."""
        course = getattr(user, "course", None)
        return cls(
            id=user.id,
            username=user.username,
            name=user.name or None,
            role=user.role,
            lab=user.lab or None,
            matriculation_no=(user.matriculation_no or None) if user.role == user.Role.STUDENT else None,
            course_name=course.name if course is not None else None,
        )


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
