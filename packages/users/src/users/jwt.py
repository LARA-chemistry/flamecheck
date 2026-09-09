"""
JWT token helpers for the FlameCheck API.

Uses PyJWT (pulled in transitively) to sign short-lived access tokens and
longer-lived refresh tokens. Tokens are stateless; revocation of refresh
tokens is handled by storing a per-user ``token_version`` counter on the user
(the ``logout`` endpoint bumps it, invalidating all earlier tokens).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import jwt
from django.conf import settings
from django.utils import timezone
from ninja import errors as ninja_errors

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"


class TokenError(Exception):
    """Raised when a JWT cannot be validated."""


def _now() -> Any:
    return timezone.now()


def _token_ttl(token_type: str) -> timedelta:
    if token_type == ACCESS_TOKEN:
        return timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES)
    return timedelta(days=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS)


def issue_token(user: Any, token_type: str) -> str:
    """
    Create a signed JWT for ``user``.

    Args:
        user: An authenticated Django user instance.
        token_type: One of :data:`ACCESS_TOKEN` or :data:`REFRESH_TOKEN`.

    Returns:
        str: The encoded JWT.

    Raises:
        ValueError: If ``token_type`` is not known.

    """
    if token_type not in (ACCESS_TOKEN, REFRESH_TOKEN):
        raise ValueError(f"Unknown token type: {token_type}")
    now = _now()
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "jti": uuid.uuid4().hex,
        "type": token_type,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + _token_ttl(token_type)).timestamp()),
        "aud": settings.JWT_AUDIENCE,
        "iss": settings.JWT_ISSUER,
        "tv": getattr(user, "token_version", 0),
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")


def decode_token(token: str, expected_type: str = ACCESS_TOKEN) -> dict[str, Any]:
    """
    Validate and decode a JWT.

    Args:
        token: The encoded JWT.
        expected_type: The expected ``type`` claim (access or refresh).

    Returns:
        dict: The validated payload.

    Raises:
        TokenError: If the token is invalid, expired or of the wrong type.

    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SIGNING_KEY,
            algorithms=["HS256"],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            leeway=5,
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise TokenError("Token type mismatch")
    return payload


def validate_access_token(token: str) -> dict[str, Any]:
    """Validate an access token; returns its payload or raises a 401 error."""
    try:
        return decode_token(token, ACCESS_TOKEN)
    except TokenError as exc:
        raise ninja_errors.AuthenticationError(401, str(exc)) from exc


def validate_refresh_token(token: str) -> dict[str, Any]:
    """Validate a refresh token; returns its payload or raises a 401 error."""
    try:
        return decode_token(token, REFRESH_TOKEN)
    except TokenError as exc:
        raise ninja_errors.AuthenticationError(401, str(exc)) from exc


def token_pair(user: Any) -> dict[str, Any]:
    """Build an access/refresh token pair for ``user``."""
    return {
        "access": issue_token(user, ACCESS_TOKEN),
        "refresh": issue_token(user, REFRESH_TOKEN),
        "access_expires_in": int(settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES * 60),
        "refresh_expires_in": int(settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS * 24 * 3600),
        "token_type": "Bearer",
    }


def refresh_pair(refresh_token: str, user: Any) -> dict[str, Any]:
    """
    Rotate a refresh token into a new access/refresh pair.

    The refresh token is validated and the user's stored ``token_version`` is
    checked against the token's ``tv`` claim so revoked tokens fail.

    Args:
        refresh_token: The presented refresh token.
        user: The user the token belongs to (fetched by the caller).

    Returns:
        dict: A fresh token pair.

    Raises:
        ninja_errors.AuthenticationError: If the token is invalid or revoked.

    """
    payload = validate_refresh_token(refresh_token)
    if int(payload["sub"]) != user.id:
        raise ninja_errors.AuthenticationError(401, "Token does not belong to this user.")
    if int(payload.get("tv", 0)) != int(getattr(user, "token_version", 0)):
        raise ninja_errors.AuthenticationError(401, "Token has been revoked.")
    return token_pair(user)
