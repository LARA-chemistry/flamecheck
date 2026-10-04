from django.db import models
from django.utils.translation import gettext_lazy as _


class Course(models.Model):
    """
    A lab course / semester (e.g. 'Inorganic Chemistry WS 2026, Biology track').

    Students are enrolled in a course; analyses are assigned per course.
    """

    name = models.CharField(max_length=255, unique=True, help_text=_("Course name (unique)."))
    semester = models.CharField(max_length=64, blank=True, default="", help_text=_("Semester label (e.g. 'WS 2026')."))
    track = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_("Specialisation track (biology, pharmacy, materials science, ...)."),
    )
    is_active = models.BooleanField(default=True, help_text=_("Only active courses are offered to students."))

    class Meta:
        verbose_name = _("Course")
        verbose_name_plural = _("Courses")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class GradingConfig(models.Model):
    """
    Grading configuration.

    One global default row (``course=None``) plus at most one overriding row
    per course (see :meth:`get_for_course`).
    """

    points_per_correct_ion = models.PositiveSmallIntegerField(
        default=10,
        help_text=(
            "Points per correctly identified ion in per-ion mode; points per "
            "completed analysis (all ions exact) in per-analysis mode."
        ),
    )
    passing_score = models.PositiveIntegerField(
        default=50,
        help_text=_(
            "Minimum total points a student needs across all analyses of the "
            "course to pass it (0 disables the pass check)."
        ),
    )
    penalty_second_submission = models.PositiveSmallIntegerField(
        default=2,
        help_text=_("Points deducted when the 2nd submission corrects a miss (per-ion mode)."),
    )
    penalty_third_submission = models.PositiveSmallIntegerField(
        default=4,
        help_text=_("Points deducted when the 3rd submission corrects a miss (per-ion mode)."),
    )
    false_positive_deduction = models.PositiveSmallIntegerField(
        default=0,
        help_text=_("Points deducted per wrongly selected ion (0 disables)."),
    )
    retry_point_deduction = models.PositiveSmallIntegerField(
        default=0,
        help_text=_(
            "'New analysis' mode: points subtracted from the course total for each "
            "earlier (superseded) re-trial attempt (0 disables the penalty)."
        ),
    )
    grading_mode = models.CharField(
        max_length=16,
        choices=[
            ("per_ion", _("Per ion (default)")),
            ("per_analysis", _("Per analysis (all-or-nothing)")),
        ],
        default="per_ion",
        help_text=_("Scoring mode: award points per correct ion, or only if the whole set is exact."),
    )
    submission_mode = models.CharField(
        max_length=16,
        choices=[
            ("resubmit", _("Resubmit (default)")),
            ("new_analysis", _("New analysis on wrong submission")),
        ],
        default="resubmit",
        help_text=_(
            "How a wrong submission is handled: allow resubmissions on the same "
            "analysis, or hand out a fresh random analysis of the same type "
            "(up to the type's max repetitions)."
        ),
    )
    max_submissions_per_analysis = models.PositiveSmallIntegerField(
        default=3,
        help_text=_("Maximum number of submissions allowed per analysis instance."),
    )
    final_score_strategy = models.CharField(
        max_length=8,
        choices=[
            ("best", _("Best submission")),
            ("last", _("Last submission")),
        ],
        default="best",
        help_text=_("How the final score is derived when multiple submissions exist."),
    )
    # ---- multiple choice (per course) ---------------------------------------
    mc_points_per_card = models.PositiveSmallIntegerField(
        default=10,
        help_text=_("Multiple choice: points awarded per card when every question is answered correctly."),
    )
    mc_penalty_per_wrong = models.PositiveSmallIntegerField(
        default=2,
        help_text=_("Multiple choice: points deducted for each wrongly answered question on a card."),
    )
    course = models.ForeignKey(
        "config.Course",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="grading_configs",
        help_text=_(
            "Course this grading configuration belongs to. Null is the global "
            "default used by any course without its own configuration."
        ),
    )

    class Meta:
        verbose_name = _("Grading configuration")
        verbose_name_plural = _("Grading configurations")
        constraints = [
            models.UniqueConstraint(
                fields=["course"],
                condition=models.Q(course__isnull=False),
                name="unique_grading_config_per_course",
            ),
        ]

    def __str__(self) -> str:
        scope = f" ({self.course.name})" if self.course_id else ""
        unit = "pts/analysis" if self.grading_mode == "per_analysis" else "pts/ion"
        return (
            f"Grading{scope} ({self.grading_mode}, {self.points_per_correct_ion} {unit}, "
            f"pass >= {self.passing_score}, max {self.max_submissions_per_analysis})"
        )

    @classmethod
    def get_instance(cls) -> "GradingConfig":
        """Return (creating if necessary) the global (default) grading configuration."""
        instance = cls.objects.filter(course__isnull=True).order_by("id").first()
        if instance is None:
            instance = cls.objects.create(course=None)
        return instance

    @classmethod
    def get_for_course(cls, course) -> "GradingConfig":
        """
        Return the grading configuration that applies to ``course``.

        Returns the course's own configuration if one exists, otherwise the
        global default. The global default is created on demand.
        """
        if course is not None:
            own = cls.objects.filter(course=course).first()
            if own is not None:
                return own
        return cls.get_instance()

    def ideal_score(self, correct_ion_count: int) -> int:
        """Compute the ideal (maximum) score for an analysis with ``correct_ion_count`` ions."""
        if self.grading_mode == "per_analysis":
            return int(self.points_per_correct_ion)
        return int(correct_ion_count * self.points_per_correct_ion)

    def score_submission(
        self,
        *,
        correct_ion_ids: set[int],
        selected_ion_ids: set[int],
        submission_number: int,
    ) -> dict[str, int]:
        """
        Grade one submission according to the configured mode.

        In ``per_ion`` mode every correct ion is worth ``points_per_correct_ion``
        (minus the false-positive deduction and the retry penalties). In
        ``per_analysis`` mode the submission is all-or-nothing: the full
        ``points_per_correct_ion`` value is awarded only when the selected set
        exactly matches the correct set; retry penalties do not apply.

        Args:
            correct_ion_ids: IDs of the ions actually present in the analysis.
            selected_ion_ids: IDs of the ions the student selected.
            submission_number: 1-based ordinal of this submission (penalties apply to 2nd+).

        Returns:
            dict with ``score``, ``correct_count``, ``wrong_count``, ``missing_count``,
            ``penalty`` and ``ideal_score``.

        """
        correct = selected_ion_ids & correct_ion_ids
        wrong = selected_ion_ids - correct_ion_ids
        missing = correct_ion_ids - selected_ion_ids
        penalty = 0

        if self.grading_mode == "per_analysis":
            if selected_ion_ids == correct_ion_ids:
                score = int(self.points_per_correct_ion)
            else:
                score = 0
        else:  # per_ion (default)
            score = len(correct) * int(self.points_per_correct_ion)
            if self.false_positive_deduction:
                score -= len(wrong) * int(self.false_positive_deduction)
            # Penalties apply when a later submission *improves* on the previous one:
            # the spec models this as a deduction for taking the retry.
            if submission_number == 2:
                penalty = int(self.penalty_second_submission)
            elif submission_number >= 3:
                penalty = int(self.penalty_third_submission)
            score -= penalty
            score = max(0, score)

        return {
            "score": score,
            "correct_count": len(correct),
            "wrong_count": len(wrong),
            "missing_count": len(missing),
            "penalty": penalty,
            "ideal_score": self.ideal_score(len(correct_ion_ids)),
        }


class AppSettingsManager(models.Manager["AppSettings"]):
    """Manager for the singleton :class:`AppSettings`."""

    def get_or_create_instance(self) -> "AppSettings":
        """Return (creating if missing) the singleton settings row."""
        instance, _ = self.get_or_create(pk=1)
        return instance


class AssistantCourse(models.Model):
    """Assignment of a course to an assistant (which courses they may support)."""

    assistant = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="assistant_courses",
        help_text=_("Assistant responsible for this course."),
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="assistants",
        help_text=_("Course the assistant supports."),
    )

    class Meta:
        verbose_name = _("Assistant course assignment")
        verbose_name_plural = _("Assistant course assignments")
        constraints = [
            models.UniqueConstraint(
                fields=["assistant", "course"],
                name="unique_assistant_course",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assistant.username} → {self.course.name}"


class AppSettings(models.Model):
    """Singleton global application settings (points per analysis, analyses per course)."""

    class Registration(models.TextChoices):
        """How new student accounts are created (mutually exclusive)."""

        MANUAL = "manual", _("Manual (created by an admin in Admin → Courses → Members)")
        SELF_REGISTRATION = "self_registration", _("Self-registration (students register + confirm their e-mail)")
        OAUTH = "oauth", _("OAuth (students sign in via an external identity provider)")

    registration = models.CharField(
        max_length=24,
        choices=Registration.choices,
        default=Registration.MANUAL,
        help_text=(
            "How new student accounts are created. Exactly one mode is active at a time: "
            "manual (admin creates accounts), self-registration (students register and confirm "
            "their e-mail) or OAuth (students sign in via an external provider and complete a "
            "registration page)."
        ),
    )
    points_per_analysis = models.PositiveSmallIntegerField(
        default=10,
        help_text=_("Points per correctly identified analysis (per-analysis mode)."),
    )
    analyses_per_course = models.PositiveSmallIntegerField(
        default=3,
        help_text=_("Number of analyses (announcements) per student per course."),
    )
    active_course = models.ForeignKey(
        Course,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="plus_active_settings",
        help_text=_("Currently active course (the one students see after login)."),
    )
    # ---- database backup -----------------------------------------------------
    backup_enabled = models.BooleanField(
        default=False,
        help_text=_("Run a scheduled database backup (in-process scheduler)."),
    )
    backup_interval_minutes = models.PositiveIntegerField(
        default=60,
        help_text=_("Minutes between scheduled backups (minimum 1)."),
    )
    backup_location = models.CharField(
        max_length=500,
        default="backups",
        blank=True,
        help_text=_(
            "Directory for backup files. Relative paths are resolved against the "
            "project root (e.g. 'backups' or '/var/backups/flamecheck')."
        ),
    )
    backup_keep = models.PositiveIntegerField(
        default=10,
        help_text=_("Number of backups to keep; older ones are deleted after each backup."),
    )
    last_backup_at = models.DateTimeField(null=True, blank=True)
    last_backup_file = models.CharField(max_length=255, blank=True, default="")
    last_restore_at = models.DateTimeField(null=True, blank=True)
    last_restore_file = models.CharField(max_length=255, blank=True, default="")
    # ---- login-page branding ------------------------------------------------
    # A university/institut logo shown in the upper-right corner of the login
    # page (SVG or PNG). ``FileField`` (not ``ImageField``) because SVG is not
    # raster-validated by Pillow.
    login_logo = models.FileField(
        upload_to="branding",
        null=True,
        blank=True,
        help_text=_("Optional university/institut logo (SVG or PNG) shown on the login page."),
    )
    # A QR code of the main login-page URL (SVG or PNG), shown below the login
    # card on wide screens so a smartphone can be used to log in.
    login_qr = models.FileField(
        upload_to="branding",
        null=True,
        blank=True,
        help_text=_("Optional QR code (SVG or PNG) of the login URL, shown on wide screens."),
    )
    objects = AppSettingsManager()

    class Meta:
        verbose_name = _("Application settings")
        verbose_name_plural = _("Application settings")

    def __str__(self) -> str:
        return f"AppSettings (course={self.active_course}, analyses={self.analyses_per_course})"

    @classmethod
    def get_instance(cls) -> "AppSettings":
        """Return (creating if necessary) the singleton settings row."""
        return cls.objects.get_or_create_instance()

    @classmethod
    def get_registration_mode(cls) -> str:
        """
        Return the active registration mode without creating a settings row.

        Returns:
            str: One of :class:`AppSettings.Registration` values; ``"manual"`` when no
                settings row exists yet (e.g. a brand-new database).

        """
        instance = cls.objects.first()
        return instance.registration if instance is not None else cls.Registration.MANUAL
