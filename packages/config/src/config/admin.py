from django.contrib import admin

from .models import AppSettings, Course, GradingConfig


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for courses."""

    list_display = ["name", "semester", "track", "is_active"]
    list_filter = ["is_active", "semester"]
    search_fields = ["name"]


@admin.register(GradingConfig)
class GradingConfigAdmin(admin.ModelAdmin):
    """Admin for the singleton grading configuration."""

    list_display = ["__str__"]


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    """Admin for the singleton application settings."""

    list_display = ["__str__"]
