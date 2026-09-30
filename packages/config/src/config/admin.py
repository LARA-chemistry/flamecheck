from django.contrib import admin

from .models import AppSettings, Course, GradingConfig


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for courses."""

    list_display = ["name", "semester", "track", "is_active"]
    list_filter = ["is_active", "semester"]
    list_editable = ["is_active"]
    search_fields = ["name"]


@admin.register(GradingConfig)
class GradingConfigAdmin(admin.ModelAdmin):
    """
    Admin for the singleton grading configuration.

    The single row is editable directly in the change list, so every grading
    setting can be changed without opening the object.
    """

    list_display = [
        "__str__",
        "grading_mode",
        "points_per_correct_ion",
        "penalty_second_submission",
        "penalty_third_submission",
        "false_positive_deduction",
        "max_submissions_per_analysis",
        "final_score_strategy",
    ]
    list_display_links = ["__str__"]  # summary column links; settings columns stay editable
    list_editable = [
        "grading_mode",
        "points_per_correct_ion",
        "penalty_second_submission",
        "penalty_third_submission",
        "false_positive_deduction",
        "max_submissions_per_analysis",
        "final_score_strategy",
    ]


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    """
    Admin for the singleton application settings.

    The single row is editable directly in the change list.
    """

    list_display = ["__str__", "points_per_analysis", "analyses_per_course", "active_course"]
    list_display_links = ["__str__"]  # summary column links; settings columns stay editable
    list_editable = ["points_per_analysis", "analyses_per_course", "active_course"]
