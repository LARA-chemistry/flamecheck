from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MultichoiceConfig(AppConfig):
    """FlameCheck multiple-choice app (questions, cards, sheets, submissions, grading)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "multichoice"
    verbose_name = _("Multiple choice")
