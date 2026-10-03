"""Ninja API for login-page branding (university logo + login QR code)."""

from __future__ import annotations

import io
import logging
import os

from django.core.files import File
from ninja import File as NinjaFile
from ninja import Router, Schema
from ninja.errors import AuthenticationError, HttpError
from ninja.files import UploadedFile
from users.models import User

from ..models import AppSettings


class BrandingOut(Schema):
    """Public login-page branding: the logo / QR URLs (each nullable)."""

    login_logo: str | None = None
    login_qr: str | None = None


logger = logging.getLogger(__name__)

# 512 KB is plenty for an SVG logo / QR and keeps uploads cheap.
MAX_UPLOAD_BYTES = 512_000
ALLOWED_LOGO_EXT = {".svg"}
ALLOWED_QR_EXT = {".svg", ".png"}


def _admin_user(request) -> User:
    """Return the authenticated admin user or raise 403/401."""
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    if not user.is_admin:
        raise HttpError(403, "Admin access required.")
    return user


def _storage_url(field) -> str | None:
    """Public URL for a FileField value, or ``None`` when empty."""
    if field and field.name:
        return field.url
    return None


def _write_upload(instance: AppSettings, attr: str, uploaded: UploadedFile, allowed_ext: set[str]) -> None:
    """
    Validate and store an uploaded file in ``instance.attr`` (replacing any old one).

    Only the allowed extensions are accepted; the on-disk filename is fixed to a
    stable name so the URL is constant and the old file is overwritten rather
    than accumulating.
    """
    name = uploaded.name or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in allowed_ext:
        allowed = ", ".join(sorted(allowed_ext))
        raise HttpError(400, f"Unsupported file type. Allowed: {allowed}.")
    data = uploaded.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HttpError(400, f"File too large (max {MAX_UPLOAD_BYTES // 1024} KB).")
    current = getattr(instance, attr)
    if current:
        current.delete(save=False)
    setattr(instance, attr, File(io.BytesIO(data), name=f"branding/{attr}{ext}"))
    instance.save()


def _clear(instance: AppSettings, attr: str) -> None:
    """Remove a stored file and clear ``instance.attr``."""
    current = getattr(instance, attr)
    if current:
        current.delete(save=False)
    setattr(instance, attr, None)
    instance.save()


router = Router(tags=["branding"])


def _branding_payload(s: AppSettings) -> dict[str, str | None]:
    """The public branding payload (logo / QR URLs) for the settings row."""
    return {"login_logo": _storage_url(s.login_logo), "login_qr": _storage_url(s.login_qr)}


@router.get("/branding", auth=None, response=BrandingOut)
def get_branding(request) -> dict[str, str | None]:
    """
    Public login-page branding (no auth required).

    Returns the URLs of the university/institut logo and the login QR code.
    Either may be ``null`` when not configured; the client then hides the
    corresponding element.
    """
    s = AppSettings.get_instance()
    return _branding_payload(s)


@router.post("/admin/branding/logo", response=BrandingOut)
def upload_logo(request, file: UploadedFile = NinjaFile(...)) -> dict[str, str | None]:  # noqa: B008
    """Upload the university/institut login logo (SVG only, admin)."""
    user = _admin_user(request)
    s = AppSettings.get_instance()
    _write_upload(s, "login_logo", file, ALLOWED_LOGO_EXT)
    logger.info("Admin %s updated the login logo", user.username)
    return _branding_payload(s)


@router.post("/admin/branding/qr", response=BrandingOut)
def upload_qr(request, file: UploadedFile = NinjaFile(...)) -> dict[str, str | None]:  # noqa: B008
    """Upload the login-page QR code (SVG or PNG, admin)."""
    user = _admin_user(request)
    s = AppSettings.get_instance()
    _write_upload(s, "login_qr", file, ALLOWED_QR_EXT)
    logger.info("Admin %s updated the login QR code", user.username)
    return _branding_payload(s)


@router.delete("/admin/branding/logo", response=BrandingOut)
def remove_logo(request) -> dict[str, str | None]:
    """Remove the university/institut login logo (admin)."""
    user = _admin_user(request)
    s = AppSettings.get_instance()
    _clear(s, "login_logo")
    logger.info("Admin %s removed the login logo", user.username)
    return _branding_payload(s)


@router.delete("/admin/branding/qr", response=BrandingOut)
def remove_qr(request) -> dict[str, str | None]:
    """Remove the login-page QR code (admin)."""
    user = _admin_user(request)
    s = AppSettings.get_instance()
    _clear(s, "login_qr")
    logger.info("Admin %s removed the login QR code", user.username)
    return _branding_payload(s)
