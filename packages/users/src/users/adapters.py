from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)


def _registration_mode() -> str:
    """Return the active registration mode without requiring a settings row."""
    from config.models import AppSettings

    return AppSettings.get_registration_mode()


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        """
        Allow OAuth sign-ups only while the registration mode is ``oauth``.

        This is the gate that decides whether a brand-new identity from an
        external provider may create a FlameCheck account.
        """
        return _registration_mode() == "oauth"

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populate a new user from social provider data.

        Every OAuth-created account is a *student* that still has to complete
        the registration page (course + metadata + generated analyses), so
        ``role`` is forced to student and ``registered`` starts False.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.first_name and not user.last_name:
            if name := data.get("name"):
                parts = str(name).strip().split(None, 1)
                user.first_name = parts[0] if parts else ""
                user.last_name = parts[1] if len(parts) > 1 else ""
            else:
                user.first_name = str(data.get("first_name") or "")
                user.last_name = str(data.get("last_name") or "")
        user.role = user.Role.STUDENT
        user.registered = False
        return user
