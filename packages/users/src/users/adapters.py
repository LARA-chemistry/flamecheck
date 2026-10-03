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


def _onboarding_mode() -> str:
    """Return the active onboarding mode without requiring a settings row."""
    from config.models import AppSettings

    return AppSettings.get_onboarding_mode()


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        """
        Allow OAuth sign-ups only while the onboarding mode is ``oauth``.

        This is the gate that decides whether a brand-new identity from an
        external provider may create a FlameCheck account.
        """
        return _onboarding_mode() == "oauth"

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populate a new user from social provider data.

        Every OAuth-created account is a *student* that still has to complete
        the onboarding page (course + metadata + generated analyses), so
        ``role`` is forced to student and ``onboarded`` starts False.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        user.role = user.Role.STUDENT
        user.onboarded = False
        return user
