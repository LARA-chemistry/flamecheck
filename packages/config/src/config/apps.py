from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ConfigConfig(AppConfig):
    """FlameCheck configuration app (courses, grading settings)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "config"
    verbose_name = _("Configuration")
