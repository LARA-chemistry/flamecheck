from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm, UserAdminCreationForm
from .models import LoginAttempt, StudentAssignment, StudentBarcode, User


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    """Admin for the custom user model with role, course and barcode info."""

    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Profile"),
            {
                "fields": (
                    "name",
                    "email",
                    "telephone",
                    "role",
                    "matriculation_no",
                    "lab",
                    "labspace_id",
                    "course",
                )
            },
        ),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["username", "name", "role", "course", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["name", "username", "matriculation_no"]


@admin.register(StudentBarcode)
class StudentBarcodeAdmin(admin.ModelAdmin):
    """Admin for student barcodes."""

    list_display = ["value", "student", "active", "created_at"]
    search_fields = ["value", "student__username"]
    list_filter = ["active"]


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Read-only audit view of login attempts."""

    list_display = ["username", "ip_address", "success", "attempted_at"]
    list_filter = ["success"]
    search_fields = ["username", "ip_address"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudentAssignment)
class StudentAssignmentAdmin(admin.ModelAdmin):
    """Admin for student - analysis assignments."""

    list_display = ["student", "instance", "number", "course"]
    search_fields = ["student__username"]
    list_filter = ["course"]
