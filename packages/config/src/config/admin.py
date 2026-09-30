"""
Admin for the configuration app (courses + the two settings singletons).

Each settings model has a dedicated change form (its "own edit workflow") with
the fields grouped into clearly-labelled fieldsets, plus a readable change
list that doubles as a quick-edit surface and links to the full editor.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AppSettings, Course, GradingConfig


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for courses (name, semester, track, active)."""

    list_display = ["name", "semester", "track", "is_active"]
    list_filter = ["is_active", "semester"]
    list_editable = ["is_active"]
    search_fields = ["name"]


@admin.register(GradingConfig)
class GradingConfigAdmin(admin.ModelAdmin):
    """
    Admin for the singleton grading configuration.

    The change form (the row link / "Change" button) is the primary edit
    workflow, with the fields grouped into labelled sections. The change list
    stays as a compact quick-edit dashboard.
    """

    list_display = [
        "__str__",
        "grading_mode",
        "points_per_correct_ion",
        "max_submissions_per_analysis",
        "final_score_strategy",
    ]
    list_display_links = ["__str__"]
    list_editable = [
        "grading_mode",
        "points_per_correct_ion",
        "max_submissions_per_analysis",
        "final_score_strategy",
    ]
    fieldsets = (
        (
            _("Scoring mode"),
            {
                "classes": ("wide",),
                "fields": ("grading_mode", "final_score_strategy", "points_per_correct_ion"),
            },
        ),
        (
            _("Penalties & limits"),
            {
                "classes": ("wide",),
                "fields": (
                    "penalty_second_submission",
                    "penalty_third_submission",
                    "false_positive_deduction",
                    "max_submissions_per_analysis",
                ),
            },
        ),
    )


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    """
    Admin for the singleton application settings.

    The change form is the primary edit workflow; the change list is a compact
    quick-edit dashboard.
    """

    list_display = ["__str__", "points_per_analysis", "analyses_per_course", "active_course"]
    list_display_links = ["__str__"]
    list_editable = ["points_per_analysis", "analyses_per_course", "active_course"]
    fieldsets = (
        (
            _("Points"),
            {"classes": ("wide",), "fields": ("points_per_analysis",)},
        ),
        (
            _("Course setup"),
            {
                "classes": ("wide",),
                "fields": ("analyses_per_course", "active_course"),
            },
        ),
    )
