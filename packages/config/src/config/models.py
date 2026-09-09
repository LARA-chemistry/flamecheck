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
    """Singleton grading configuration (admin-adjustable)."""

    points_per_correct_ion = models.PositiveSmallIntegerField(
        default=10,
        help_text=_("Points awarded per correctly identified ion (per-ion mode)."),
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
    grading_mode = models.CharField(
        max_length=16,
        choices=[
            ("per_ion", _("Per ion (default)")),
            ("per_analysis", _("Per analysis (all-or-nothing)")),
        ],
        default="per_ion",
        help_text=_("Scoring mode: award points per correct ion, or only if the whole set is exact."),
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

    class Meta:
        verbose_name = _("Grading configuration")
        verbose_name_plural = _("Grading configurations")

    def __str__(self) -> str:
        return f"Grading ({self.grading_mode}, {self.points_per_correct_ion} pts/ion, max {self.max_submissions_per_analysis})"

    @classmethod
    def get_instance(cls) -> "GradingConfig":
        """Return (creating if necessary) the singleton grading configuration."""
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

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
