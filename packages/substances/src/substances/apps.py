from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SubstancesConfig(AppConfig):
    """FlameCheck substances app (ion and substance catalogs)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "substances"
    verbose_name = _("Substances")
