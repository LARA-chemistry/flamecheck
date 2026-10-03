import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def generate_labspace_id() -> str:
    """
    Return a random labspace id.

    Used during onboarding when the student (or their OAuth provider) did not
    supply a labspace number, e.g. ``LS-1A2B3C4D``.

    Returns:
        str: A fresh, unique labspace identifier.

    """
    return f"LS-{uuid.uuid4().hex[:8].upper()}"


class User(AbstractUser):
    """FlameCheck user with a role (student, assistant or admin)."""

    class Role(models.TextChoices):
        """Available user roles."""

        STUDENT = "student", _("Student")
        ASSISTANT = "assistant", _("Assistant")
        ADMIN = "admin", _("Admin")

    name = models.CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text=_("Role of the user in the system."),
    )
    matriculation_no = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_("Matriculation number (students only)."),
    )
    lab = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=_("Assigned lab / lab course (e.g. 'Inorganic Chemistry, Biology track')."),
    )
    labspace_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_("Labspace identification (institutional user id)."),
    )
    telephone = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_("Telephone / mobile number (e.g. for practical contact)."),
    )
    course = models.ForeignKey(
        "config.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
        help_text=_("Course the student is enrolled in (students only)."),
    )
    token_version = models.PositiveIntegerField(
        default=0,
        help_text=_("Bumped on logout to revoke all issued JWTs."),
    )
    onboarded = models.BooleanField(
        default=True,
        help_text=(
            "Whether the user has completed onboarding. OAuth-created students start "
            "False and complete an onboarding page (course + metadata + generated analyses); "
            "manually created and self-registered accounts are onboarded by default."
        ),
    )

    # -- role helpers -------------------------------------------------------
    @property
    def is_student(self) -> bool:
        """Return True if the user is a student."""
        return self.role == self.Role.STUDENT

    @property
    def is_assistant(self) -> bool:
        """Return True if the user is an assistant."""
        return self.role == self.Role.ASSISTANT

    @property
    def is_admin(self) -> bool:
        """Return True if the user has the admin role."""
        return self.role == self.Role.ADMIN

    def get_absolute_url(self) -> str:
        """
        Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.pk})


class StudentBarcode(models.Model):
    """
    Unique barcode (Code128 / QR payload) that identifies a student.

    Scanning the barcode is the primary way students authenticate. The value
    is looked up server-side; the barcode never reveals which user it belongs
    to when it is unknown.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="barcodes",
        help_text=_("Student this barcode belongs to."),
    )
    value = models.CharField(
        max_length=128,
        unique=True,
        help_text=_("Barcode payload, e.g. 'FC-<student_id>-<uuid8>'."),
    )
    active = models.BooleanField(
        default=True,
        help_text=_("Inactive barcodes cannot be used to log in."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Student barcode")
        verbose_name_plural = _("Student barcodes")
        constraints = [
            models.UniqueConstraint(fields=["value"], name="unique_barcode_value"),
        ]

    def __str__(self) -> str:
        return f"{self.student.username} ({self.value})"


class LoginAttempt(models.Model):
    """Tracks login attempts for brute-force protection and auditing."""

    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    success = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("Login attempt")
        verbose_name_plural = _("Login attempts")
        ordering = ["-attempted_at"]


class StudentAssignment(models.Model):
    """
    Assignment of a concrete analysis instance to a student.

    Kept in the users app so the assistant can see, per course, which student
    is assigned which analysis sheet/barcode. The ``AnalysisInstance`` itself
    lives in the analyses app and references back via ``instance``.
    """

    course = models.ForeignKey(
        "config.Course",
        on_delete=models.CASCADE,
        related_name="assignments",
        help_text=_("Course this assignment belongs to."),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analysis_assignments",
        help_text=_("Student the analysis is assigned to."),
    )
    instance = models.ForeignKey(
        "analyses.AnalysisInstance",
        on_delete=models.CASCADE,
        related_name="assignments",
        help_text=_("Analysis instance (sheet) assigned to the student."),
    )
    number = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("Announcement number of this analysis within the course (e.g. 3 for the 3rd analysis)."),
    )

    class Meta:
        verbose_name = _("Student analysis assignment")
        verbose_name_plural = _("Student analysis assignments")
        constraints = [
            models.UniqueConstraint(
                fields=["student", "instance"],
                name="unique_student_instance_assignment",
            ),
            models.UniqueConstraint(
                fields=["course", "student", "number"],
                name="unique_course_student_number",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student.username}: #{self.number} ({self.instance})"
