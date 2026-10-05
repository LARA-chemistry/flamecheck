"""
E-mail-confirmation token helpers for self-registration.

A signed, timestamped token (via :mod:`django.core.signing`) identifies the user
whose e-mail is being confirmed. The token is embedded in the confirmation link
sent to the registrant; opening the link verifies it and activates the account.
Using a stateless signed token means no extra table or migration is required.
"""

from __future__ import annotations

from django.conf import settings
from django.core import signing

_SALT = "flamecheck.email-verification"


def _signer() -> signing.TimestampSigner:
    """Return the shared timestamp signer for verification tokens."""
    return signing.TimestampSigner(salt=_SALT)


def make_verification_token(username: str) -> str:
    """
    Create a signed, timestamped token for ``username``.

    Args:
        username: The username of the user to confirm.

    Returns:
        str: An URL-safe signed token embedding the username and a timestamp.

    """
    return _signer().sign(username)


def verify_token(token: str, max_age: int | None = None) -> str:
    """
    Verify a confirmation ``token`` and return the embedded username.

    Args:
        token: The signed token from the confirmation link.
        max_age: Optional maximum token age in seconds (defaults to
            :data:`~flamecheck.settings.base.EMAIL_VERIFICATION_TOKEN_MAX_AGE`).

    Returns:
        str: The username the token was issued for.

    Raises:
        signing.SignatureExpired: If the token is older than ``max_age``.
        signing.BadSignature: If the token is malformed or was not issued here.

    """
    if max_age is None:
        max_age = int(getattr(settings, "EMAIL_VERIFICATION_TOKEN_MAX_AGE", 48 * 3600))
    return _signer().unsign(token, max_age=max_age)
