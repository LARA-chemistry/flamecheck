"""Analyses domain models: types, instances and immutable submissions."""

from __future__ import annotations

import logging

from config.models import GradingConfig
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("flamecheck.audit")

# Window status values (also used by the frontend).
STATUS_OPEN = "open"
STATUS_TOO_EARLY = "too_early"
STATUS_TOO_LATE = "too_late"
STATUS_SUBMITTED = "submitted"


class AnalysisType(models.Model):
    """
    A kind of analysis (e.g. 'Analysis 3  -  cations I+II & anions').

    Defines the *possible* ion set that is shown to students. The concrete
    correct answer lives on the :class:`AnalysisInstance`.
    """

    name = models.CharField(max_length=255, unique=True, help_text=_("Type name, e.g. 'Analysis 3'."))
    description = models.TextField(blank=True, default="", help_text=_("Short description shown to students."))
    possible_ions = models.ManyToManyField(
        "substances.Ion",
        blank=True,
        related_name="analysis_types",
        help_text=_("Ions that *can* occur in this analysis type (shown to students)."),
    )
    # Default submission window for new instances of this type. Instances can
    # override it per session; this is just the starting value the admin sets
    # when defining the type.
    default_window_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Default earliest time a submission is accepted (inherited by new sessions)."),
    )
    default_window_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Default latest time a submission is accepted (inherited by new sessions)."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Analysis type")
        verbose_name_plural = _("Analysis types")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AnalysisInstanceManager(models.Manager["AnalysisInstance"]):
    """Business-logic manager for :class:`AnalysisInstance`."""

    def for_student(self, student) -> models.QuerySet[AnalysisInstance]:
        """All instances assigned to ``student`` (via their assignments)."""
        return (
            self.get_queryset()
            .filter(assignments__student=student)
            .prefetch_related("type", "correct_ions", "assignments", "submissions")
            .distinct()
            .order_by("assignments__number", "window_start")
        )


class AnalysisInstance(models.Model):
    """
    A concrete analysis assigned to a student, with a time window.

    The correct ion set is *never* exposed to the student before they have
    submitted; it is only revealed through the result endpoint after the
    first accepted submission.
    """

    type = models.ForeignKey(
        AnalysisType,
        on_delete=models.PROTECT,
        related_name="instances",
        help_text=_("Analysis type (defines the possible ion set)."),
    )
    correct_ions = models.ManyToManyField(
        "substances.Ion",
        blank=True,
        related_name="instances",
        help_text=_("Ions actually present in this concrete analysis (the answer key)."),
    )
    assigned_substances = models.ManyToManyField(
        "substances.Substance",
        blank=True,
        related_name="instances",
        help_text=_(
            "Substances randomly assigned to this student for the analysis (the salts to "
            "prepare / reference), recorded when the answer key is randomized."
        ),
    )
    window_start = models.DateTimeField(help_text=_("Earliest time a submission is accepted (inclusive)."))
    window_end = models.DateTimeField(help_text=_("Latest time a submission is accepted (inclusive)."))
    number = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("Announcement number within the course (e.g. 3 for the 3rd analysis)."),
    )
    course = models.ForeignKey(
        "config.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analysis_instances",
        help_text=_("Course this instance belongs to (used by assistants)."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    objects = AnalysisInstanceManager()

    class Meta:
        verbose_name = _("Analysis instance")
        verbose_name_plural = _("Analysis instances")
        ordering = ["number", "window_start"]

    def __str__(self) -> str:
        return f"{self.type.name} (#{self.number}, {self.window_start:%Y-%m-%d %H:%M}  -  {self.window_end:%H:%M})"

    # -- status / scoring --------------------------------------------------
    def window_status(self) -> str:
        """
        Return the current window status for this instance.

        Returns one of ``open``, ``too_early``, ``too_late`` or ``submitted``.
        """
        if self.submissions.exists():
            return STATUS_SUBMITTED
        now = timezone.now()
        if now < self.window_start:
            return STATUS_TOO_EARLY
        if now > self.window_end:
            return STATUS_TOO_LATE
        return STATUS_OPEN

    def submission_count(self) -> int:
        """Number of submissions made for this instance."""
        return self.submissions.count()

    def grading_config(self) -> GradingConfig:
        """
        The grading configuration that applies to this instance.

        Uses the course's own configuration when the instance belongs to a
        course that has one, otherwise the global default.
        """
        return GradingConfig.get_for_course(self.course)

    def submission_limit(self) -> int:
        """Maximum number of submissions allowed (from the applicable grading config)."""
        return int(self.grading_config().max_submissions_per_analysis)

    def score(self) -> int | None:
        """Final score for this instance, or None if no submissions yet."""
        submissions = list(self.submissions.order_by("submitted_at"))
        if not submissions:
            return None
        grading = self.grading_config()
        if grading.final_score_strategy == "last":
            return submissions[-1].score
        return max(s.score for s in submissions)

    def ideal_score(self) -> int:
        """Maximum achievable score for this instance."""
        return self.grading_config().ideal_score(self.correct_ions.count())

    # -- submission (atomic, idempotent, rate-safe) -------------------------
    def submit(
        self,
        student,
        selected_ion_ids: list[int],
        *,
        idempotency_key: str,
    ) -> Submission:
        """
        Create and grade a submission for ``student`` atomically.

        Validates ownership, time window, submission limit and that all
        selected ions belong to the possible ion set. Enforces idempotency:
        replaying the same ``idempotency_key`` returns the original
        submission instead of creating a new one.

        Args:
            student: The authenticated student user.
            selected_ion_ids: IDs of the ions the student selected.
            idempotency_key: Client-generated key preventing duplicate submissions.

        Returns:
            Submission: The (existing or newly created) submission.

        Raises:
            PermissionDenied: If the student is not assigned to this instance.
            ValidationError: If the window is closed, the limit is reached,
                or a selected ion is not part of the possible ion set.

        """
        from django.core.exceptions import PermissionDenied, ValidationError

        # 1. ownership
        if not self.assignments.filter(student=student).exists():
            logger.warning("Submission denied: %s not assigned to %s", student.username, self)
            raise PermissionDenied("You are not assigned to this analysis.")

        # 2. time window
        now = timezone.now()
        if now < self.window_start:
            logger.info("Submission rejected (too early): %s on %s", student.username, self)
            raise ValidationError(_("The submission window has not opened yet (zu früh!)."))
        if now > self.window_end:
            logger.info("Submission rejected (too late): %s on %s", student.username, self)
            raise ValidationError(_("The submission window is closed (zu spät!)."))

        # 3. idempotency (checked inside the transaction below)
        existing = Submission.objects.filter(
            analysis_instance=self,
            student=student,
            idempotency_key=idempotency_key,
        ).first()
        if existing is not None:
            return existing

        # 4. limit
        if self.submissions.count() >= self.submission_limit():
            logger.info("Submission rejected (limit reached): %s on %s", student.username, self)
            raise ValidationError(_("You have already reached the maximum number of submissions."))

        # 5. allowed ions (must be a subset of the possible ion set)
        allowed = set(self.type.possible_ions.values_list("id", flat=True))
        unknown = [i for i in selected_ion_ids if i not in allowed]
        if unknown:
            raise ValidationError({"ion_ids": [f"Ions not allowed for this analysis: {unknown}"]})

        with transaction.atomic():
            # Re-check idempotency inside the transaction to be safe under
            # concurrent replays (UniqueConstraint is the final guard).
            existing = Submission.objects.filter(
                analysis_instance=self,
                student=student,
                idempotency_key=idempotency_key,
            ).first()
            if existing is not None:
                return existing

            submission_number = self.submissions.count() + 1
            correct_ids = set(self.correct_ions.values_list("id", flat=True))
            selected_set = set(selected_ion_ids)
            grading = self.grading_config()
            result = grading.score_submission(
                correct_ion_ids=correct_ids,
                selected_ion_ids=selected_set,
                submission_number=submission_number,
            )
            try:
                submission = Submission.objects.create(
                    analysis_instance=self,
                    student=student,
                    submission_number=submission_number,
                    idempotency_key=idempotency_key,
                    score=result["score"],
                    correct_count=result["correct_count"],
                    wrong_count=result["wrong_count"],
                    missing_count=result["missing_count"],
                    penalty=result["penalty"],
                    ideal_score=result["ideal_score"],
                )
            except IntegrityError:
                # Concurrent replay won the race; return the original.
                submission = Submission.objects.get(
                    analysis_instance=self,
                    student=student,
                    idempotency_key=idempotency_key,
                )
                return submission
            submission.selected_ions.set(selected_ion_ids)
            logger.info(
                "Submission %d accepted for %s on %s: score=%s correct=%s wrong=%s missing=%s",
                submission.id,
                student.username,
                self,
                submission.score,
                result["correct_count"],
                result["wrong_count"],
                result["missing_count"],
            )
            return submission


class SubmissionManager(models.Manager["Submission"]):
    """Manager for :class:`Submission`."""

    def for_instance(self, instance) -> models.QuerySet[Submission]:
        """All submissions for an instance, oldest first."""
        return self.get_queryset().filter(analysis_instance=instance).order_by("submitted_at", "id")


class Submission(models.Model):
    """
    An immutable, timestamped ion selection by a student.

    Once created, a submission cannot be modified (the API exposes no update
    or delete operations) and is used for auditing.
    """

    analysis_instance = models.ForeignKey(
        AnalysisInstance,
        on_delete=models.PROTECT,
        related_name="submissions",
        help_text=_("Analysis instance this submission belongs to."),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submissions",
        help_text=_("Student who made this submission."),
    )
    selected_ions = models.ManyToManyField(
        "substances.Ion",
        blank=True,
        related_name="submissions",
        help_text=_("Ions the student selected."),
    )
    submission_number = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("1-based ordinal of this submission for the instance."),
    )
    idempotency_key = models.CharField(
        max_length=128, help_text=_("Client-generated key preventing duplicate submissions.")
    )
    score = models.PositiveIntegerField(default=0, help_text=_("Score awarded for this submission."))
    correct_count = models.PositiveIntegerField(default=0, help_text=_("Number of correctly selected ions."))
    wrong_count = models.PositiveIntegerField(
        default=0, help_text=_("Number of wrongly selected ions (false positives).")
    )
    missing_count = models.PositiveIntegerField(default=0, help_text=_("Number of correct ions the student missed."))
    penalty = models.PositiveIntegerField(default=0, help_text=_("Penalty applied for using a retry submission."))
    ideal_score = models.PositiveIntegerField(
        default=0, help_text=_("Ideal score for the analysis at submission time.")
    )
    submitted_at = models.DateTimeField(auto_now_add=True, help_text=_("UTC timestamp of the submission."))

    objects = SubmissionManager()

    class Meta:
        verbose_name = _("Submission")
        verbose_name_plural = _("Submissions")
        ordering = ["submitted_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["analysis_instance", "student", "idempotency_key"],
                name="unique_idempotency_per_student_instance",
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.id} {self.student.username} → {self.analysis_instance} ({self.submitted_at:%Y-%m-%d %H:%M}Z)"

    def ion_breakdown(self) -> dict[str, list[int]]:
        """Return the correct / wrong / missing ion id sets for this submission."""
        correct_ids = set(self.analysis_instance.correct_ions.values_list("id", flat=True))
        selected = set(self.selected_ions.values_list("id", flat=True))
        return {
            "correct": sorted(selected & correct_ids),
            "wrong": sorted(selected - correct_ids),
            "missing": sorted(correct_ids - selected),
        }


def student_course_result(student, course=None) -> dict:
    """
    Compute the course result for ``student``.

    Aggregates the student's final scores (see :meth:`AnalysisInstance.score`)
    across all analyses of their course — including instances without a course
    link — and compares the total with the course's passing score from the
    applicable :class:`~config.models.GradingConfig`.

    Args:
        student: The student user.
        course: The course to aggregate over (defaults to the student's course).

    Returns:
        dict with ``instances`` (the aggregated :class:`AnalysisInstance`
        objects), ``total_score``, ``ideal_score``, ``passing_score`` and
        ``passed`` (True when the total reaches the passing score; always True
        when the passing score is 0).

    """
    if course is None:
        course = getattr(student, "course", None)
    grading = GradingConfig.get_for_course(course)
    instances = [
        i
        for i in AnalysisInstance.objects.for_student(student)
        if course is None or i.course_id == course.id or i.course is None
    ]
    total = sum(i.score() or 0 for i in instances)
    ideal = sum(i.ideal_score() for i in instances)
    passing = int(grading.passing_score)
    return {
        "instances": instances,
        "total_score": total,
        "ideal_score": ideal,
        "passing_score": passing,
        "passed": passing <= 0 or total >= passing,
    }
