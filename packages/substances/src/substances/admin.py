from django.contrib import admin

from .models import Ion, Substance


class IonInline(admin.TabularInline):
    """Inline ion list for the substance admin."""

    model = Ion.substances.through
    extra = 0


@admin.register(Ion)
class IonAdmin(admin.ModelAdmin):
    """Admin for the ion catalog."""

    list_display = ["symbol", "name", "kind", "charge", "group"]
    list_filter = ["kind", "group"]
    search_fields = ["symbol", "name"]


@admin.register(Substance)
class SubstanceAdmin(admin.ModelAdmin):
    """Admin for the substance catalog."""

    list_display = ["name", "formula", "ions_summary", "pubchem_id"]
    search_fields = ["name", "formula", "synonyms"]
    filter_horizontal = ["ions"]

    @admin.display(description="Ions")
    def ions_summary(self, obj):
        return ", ".join(i.symbol for i in obj.ions.all())
