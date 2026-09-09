"""JWT bearer-token authentication for the Django Ninja API."""

from __future__ import annotations

from typing import Any

from ninja import errors as ninja_errors
from ninja.security import HttpBearer
from users import jwt
from users.models import User


class JWTBearerAuth(HttpBearer):
    """
    Validate the ``Authorization: Bearer <access-token>`` header.

    Overrides ``__call__`` to set ``request.user`` directly, bypassing
    ninja's auth machinery that may not propagate the authenticated user
    correctly in all Django 6 / ninja 1.5 combinations.
    """

    def __call__(self, request) -> Any:
        """
        Validate the token and set ``request.user``.

        Args:
            request: The Django request.

        Returns:
            The authenticated user, or ``None`` (→ 401).

        """
        headers = request.headers
        auth_value = headers.get(self.header)
        if not auth_value:
            return None
        parts = auth_value.split(" ")
        if parts[0].lower() != self.openapi_scheme:
            return None
        token = " ".join(parts[1:])
        try:
            payload = jwt.validate_access_token(token)
        except ninja_errors.AuthenticationError:
            return None
        user = User.objects.filter(pk=int(payload["sub"]), is_active=True).first()
        if user is None:
            return None
        if int(payload.get("tv", 0)) != int(getattr(user, "token_version", 0)):
            return None
        request.user = user
        return user

    def authenticate(self, request, token: str) -> Any:
        """Abstract method stub (satisfied by ``__call__`` override)."""
        raise NotImplementedError
