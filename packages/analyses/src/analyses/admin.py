from django.contrib import admin

from .models import AnalysisInstance, AnalysisType, Submission


class CorrectIonsInline(admin.TabularInline):
    """Inline correct-ion list for the analysis instance admin."""

    model = AnalysisInstance.correct_ions.through
    extra = 0


@admin.register(AnalysisType)
class AnalysisTypeAdmin(admin.ModelAdmin):
    """Admin for analysis types and their possible ion sets."""

    list_display = ["name", "ion_count"]
    search_fields = ["name"]
    filter_horizontal = ["possible_ions"]

    @admin.display(description="Possible ions")
    def ion_count(self, obj):
        return obj.possible_ions.count()


@admin.register(AnalysisInstance)
class AnalysisInstanceAdmin(admin.ModelAdmin):
    """Admin for concrete analysis instances (answer key + time window)."""

    list_display = ["type", "number", "course", "window_start", "window_end", "correct_ion_count"]
    list_filter = ["course", "type"]
    filter_horizontal = ["correct_ions"]
    inlines = [CorrectIonsInline]

    @admin.display(description="Correct ions")
    def correct_ion_count(self, obj):
        return obj.correct_ions.count()


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Read-only admin for immutable submissions (audit)."""

    list_display = ["id", "student", "analysis_instance", "submission_number", "score", "submitted_at"]
    list_filter = ["analysis_instance__course"]
    search_fields = ["student__username"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
