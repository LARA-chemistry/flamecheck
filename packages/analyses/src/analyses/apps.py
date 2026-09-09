from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AnalysesConfig(AppConfig):
    """FlameCheck analyses app (analysis types, instances, submissions, grading)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "analyses"
    verbose_name = _("Analyses")
