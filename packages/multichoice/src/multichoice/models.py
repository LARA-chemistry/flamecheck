"""Multiple-choice domain models: questions, cards, sheets and submissions."""

from __future__ import annotations

import logging

from config.models import GradingConfig
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("flamecheck.audit")

# Window status values (mirrored from the analyses app for the frontend).
STATUS_OPEN = "open"
STATUS_TOO_EARLY = "too_early"
STATUS_TOO_LATE = "too_late"
STATUS_SUBMITTED = "submitted"

# A card holds between 1 and this many questions (inclusive).
MAX_QUESTIONS_PER_CARD = 3


class MCQuestion(models.Model):
    """
    A single multiple-choice question in a course's question bank.

    The correct answer lives on exactly one of the question's
    :class:`MCOption` rows. ``description`` and ``remarks`` are free-text
    documentation fields (editable in the admin designer) that are never shown
    to students.
    """

    course = models.ForeignKey(
        "config.Course",
        on_delete=models.CASCADE,
        related_name="mc_questions",
        help_text=_("Course this question belongs to."),
    )
    text = models.CharField(max_length=500, help_text=_("The question statement shown to students."))
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Documentation (admin only): what the question covers, source, learning objective."),
    )
    remarks = models.TextField(
        blank=True,
        default="",
        help_text=_("Documentation (admin only): free remarks, e.g. grading notes or lab context."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Multiple-choice question")
        verbose_name_plural = _("Multiple-choice questions")
        ordering = ["id"]

    def __str__(self) -> str:
        return self.text[:60]

    def options(self) -> list[MCOption]:
        """Return the question's options in display order (the correct one last-hidden)."""
        return list(self.options_set.order_by("sort_order", "id"))

    def correct_option(self) -> MCOption | None:
        """Return the option marked correct, or ``None`` when the question has none."""
        return self.options_set.filter(is_correct=True).order_by("sort_order", "id").first()

    def public_payload(self) -> dict:
        """Serialize the question for students (options without the correct flag)."""
        return {
            "id": self.id,
            "text": self.text,
            "options": [{"id": o.id, "text": o.text, "sort_order": o.sort_order} for o in self.options()],
        }

    def result_payload(self) -> dict:
        """Serialize the question with the correct option revealed (after submission)."""
        correct_id = self.correct_option().id if self.correct_option() else None
        return {
            "id": self.id,
            "text": self.text,
            "correct_option_id": correct_id,
            "options": [
                {"id": o.id, "text": o.text, "is_correct": o.is_correct, "sort_order": o.sort_order}
                for o in self.options()
            ],
        }


class MCOption(models.Model):
    """One answer option of an :class:`MCQuestion` (exactly one is correct)."""

    question = models.ForeignKey(
        MCQuestion,
        on_delete=models.CASCADE,
        related_name="options_set",
        help_text=_("Question this option belongs to."),
    )
    text = models.CharField(max_length=500, help_text=_("Option text shown to students."))
    is_correct = models.BooleanField(
        default=False,
        help_text=_("Whether this option is the correct answer (exactly one per question)."),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        help_text=_("Display order of the option within the question."),
    )

    class Meta:
        verbose_name = _("Multiple-choice option")
        verbose_name_plural = _("Multiple-choice options")
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "sort_order"],
                name="unique_option_order_per_question",
            ),
        ]

    def __str__(self) -> str:
        return self.text[:60]


class MCCard(models.Model):
    """
    A card: a unit of 1 to :data:`MAX_QUESTIONS_PER_CARD` questions.

    A card is what a student actually answers; it is graded as a whole (the
    course's points-per-card minus the per-wrong-answer penalty). ``description``
    and ``remarks`` are admin-only documentation fields.
    """

    course = models.ForeignKey(
        "config.Course",
        on_delete=models.CASCADE,
        related_name="mc_cards",
        help_text=_("Course this card belongs to."),
    )
    title = models.CharField(max_length=255, help_text=_("Short title shown on the student's card."))
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Documentation (admin only): what the card covers."),
    )
    remarks = models.TextField(
        blank=True,
        default="",
        help_text=_("Documentation (admin only): free remarks about the card."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Multiple-choice card")
        verbose_name_plural = _("Multiple-choice cards")
        ordering = ["id"]

    def __str__(self) -> str:
        return self.title

    def questions(self) -> list[MCQuestion]:
        """Return the card's questions in their configured order."""
        return [row.question for row in self.card_questions.select_related("question").order_by("order", "id")]

    def question_count(self) -> int:
        """Number of questions on this card."""
        return self.card_questions.count()

    def clean(self) -> None:
        """Enforce the 1..3 questions-per-card rule (called via full_clean / API)."""
        count = self.card_questions.count()
        if count > MAX_QUESTIONS_PER_CARD:
            raise ValidationError({"questions": [f"A card may hold at most {MAX_QUESTIONS_PER_CARD} questions."]})
        if count < 1:
            raise ValidationError({"questions": ["A card needs at least one question."]})

    def public_payload(self) -> dict:
        """Serialize the card for students (title + questions, no correct flags)."""
        return {
            "id": self.id,
            "title": self.title,
            "questions": [q.public_payload() for q in self.questions()],
        }


class MCCardQuestion(models.Model):
    """Ordered link between a card and one of its questions."""

    card = models.ForeignKey(MCCard, on_delete=models.CASCADE, related_name="card_questions")
    question = models.ForeignKey(MCQuestion, on_delete=models.CASCADE, related_name="card_links")
    order = models.PositiveSmallIntegerField(default=0, help_text=_("Position of the question on the card."))

    class Meta:
        verbose_name = _("Card question link")
        verbose_name_plural = _("Card question links")
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["card", "question"], name="unique_question_per_card"),
        ]

    def __str__(self) -> str:
        return f"{self.card_id}:{self.question_id} (#{self.order})"


class MCSheetManager(models.Manager["MCSheet"]):
    """Business-logic manager for :class:`MCSheet`."""

    def for_student(self, student) -> models.QuerySet[MCSheet]:
        """All sheets assigned to ``student`` (via their assignments)."""
        return (
            self.get_queryset()
            .filter(assignments__student=student)
            .prefetch_related("card__card_questions__question__options_set", "assignments", "submissions")
            .distinct()
            .order_by("number", "window_start", "id")
        )


class MCSheet(models.Model):
    """
    A concrete, time-windowed presentation of a card to students.

    Mirrors :class:`analyses.AnalysisInstance`: a sheet references a card, a
    course, a submission window and an announcement number, and is assigned to
    students via :class:`MCStudentAssignment`.
    """

    card = models.ForeignKey(
        MCCard,
        on_delete=models.PROTECT,
        related_name="sheets",
        help_text=_("Card this sheet presents."),
    )
    course = models.ForeignKey(
        "config.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mc_sheets",
        help_text=_("Course this sheet belongs to (used for per-course grading)."),
    )
    window_start = models.DateTimeField(help_text=_("Earliest time a submission is accepted (inclusive)."))
    window_end = models.DateTimeField(help_text=_("Latest time a submission is accepted (inclusive)."))
    number = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("Announcement number within the course (e.g. 1 for the 1st card)."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MCSheetManager()

    class Meta:
        verbose_name = _("Multiple-choice sheet")
        verbose_name_plural = _("Multiple-choice sheets")
        ordering = ["number", "window_start"]

    def __str__(self) -> str:
        return f"{self.card.title} (#{self.number}, {self.window_start:%Y-%m-%d %H:%M} - {self.window_end:%H:%M})"

    # -- status / scoring ------------------------------------------------------
    def window_status(self) -> str:
        """Return ``open`` / ``too_early`` / ``too_late`` / ``submitted``."""
        if self.submissions.exists():
            return STATUS_SUBMITTED
        now = timezone.now()
        if now < self.window_start:
            return STATUS_TOO_EARLY
        if now > self.window_end:
            return STATUS_TOO_LATE
        return STATUS_OPEN

    def grading_config(self) -> GradingConfig:
        """The per-course (or global) grading configuration that applies here."""
        return GradingConfig.get_for_course(self.course)

    def ideal_score(self) -> int:
        """Maximum achievable score for this sheet (the course's points-per-card)."""
        return int(self.grading_config().mc_points_per_card)

    def score(self) -> int | None:
        """Final score for this sheet, or ``None`` when nothing was submitted."""
        submissions = list(self.submissions.order_by("submitted_at"))
        if not submissions:
            return None
        grading = self.grading_config()
        if grading.final_score_strategy == "last":
            return submissions[-1].score
        return max(s.score for s in submissions)

    # -- submission -------------------------------------------------------------
    def submit(self, student, answers: dict[int, int], *, idempotency_key: str) -> MCSubmission:
        """
        Create and grade a submission for ``student`` atomically.

        ``answers`` maps question id -> selected option id. Every question on the
        card must be answered. Validates ownership, the time window and the
        idempotency key (a replay returns the original submission).

        Raises:
            ValidationError: When the student is not assigned, the window is
                closed, an answer is missing, or an option does not belong to its
                question.

        """
        from django.core.exceptions import PermissionDenied

        if not self.assignments.filter(student=student).exists():
            logger.warning("MC submission denied: %s not assigned to %s", student.username, self)
            raise PermissionDenied("You are not assigned to this card.")

        now = timezone.now()
        if now < self.window_start:
            logger.info("MC submission rejected (too early): %s on %s", student.username, self)
            raise ValidationError(_("The submission window has not opened yet."))
        if now > self.window_end:
            logger.info("MC submission rejected (too late): %s on %s", student.username, self)
            raise ValidationError(_("The submission window is closed."))

        existing = MCSubmission.objects.filter(sheet=self, student=student, idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

        questions = self.questions()
        question_ids = {q.id for q in questions}
        if set(answers.keys()) != question_ids:
            missing = question_ids - set(answers.keys())
            unknown = set(answers.keys()) - question_ids
            raise ValidationError(
                {
                    "answers": [
                        f"Answer every question exactly once (missing {sorted(missing)}, unknown {sorted(unknown)})."
                    ]
                }
            )

        # Validate that every selected option belongs to its question.
        valid_options = {q.id: set(q.options_set.values_list("id", flat=True)) for q in questions}
        for qid, oid in answers.items():
            if oid not in valid_options.get(qid, set()):
                raise ValidationError({"answers": [f"Option {oid} does not belong to question {qid}."]})

        with transaction.atomic():
            existing = MCSubmission.objects.filter(sheet=self, student=student, idempotency_key=idempotency_key).first()
            if existing is not None:
                return existing

            result = self._grade(questions, answers)
            try:
                submission = MCSubmission.objects.create(
                    sheet=self,
                    student=student,
                    submission_number=self.submissions.count() + 1,
                    idempotency_key=idempotency_key,
                    answers=answers,
                    score=result["score"],
                    correct_count=result["correct_count"],
                    wrong_count=result["wrong_count"],
                    ideal_score=result["ideal_score"],
                )
            except IntegrityError:
                submission = MCSubmission.objects.get(sheet=self, student=student, idempotency_key=idempotency_key)
                return submission
            logger.info(
                "MC submission %d accepted for %s on %s: score=%s correct=%s wrong=%s",
                submission.id,
                student.username,
                self,
                submission.score,
                result["correct_count"],
                result["wrong_count"],
            )
            return submission

    def _grade(self, questions: list[MCQuestion], answers: dict[int, int]) -> dict[str, int]:
        """Grade the answers against the card's questions using the course config."""
        grading = self.grading_config()
        points_per_card = int(grading.mc_points_per_card)
        penalty_per_wrong = int(grading.mc_penalty_per_wrong)
        correct = 0
        wrong = 0
        for question in questions:
            correct_option = question.correct_option()
            chosen = answers.get(question.id)
            if correct_option is not None and chosen == correct_option.id:
                correct += 1
            else:
                wrong += 1
        score = max(0, points_per_card - penalty_per_wrong * wrong)
        return {
            "score": score,
            "correct_count": correct,
            "wrong_count": wrong,
            "ideal_score": points_per_card,
        }

    def questions(self) -> list[MCQuestion]:
        """Return the card's questions in order (delegated to the card)."""
        return self.card.questions()


class MCStudentAssignment(models.Model):
    """Assignment of a concrete multiple-choice sheet to a student."""

    course = models.ForeignKey(
        "config.Course",
        on_delete=models.CASCADE,
        related_name="mc_assignments",
        help_text=_("Course this assignment belongs to."),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mc_assignments",
        help_text=_("Student the card is assigned to."),
    )
    sheet = models.ForeignKey(
        MCSheet,
        on_delete=models.CASCADE,
        related_name="assignments",
        help_text=_("Sheet (card presentation) assigned to the student."),
    )
    number = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("Announcement number within the course."),
    )

    class Meta:
        verbose_name = _("Student multiple-choice assignment")
        verbose_name_plural = _("Student multiple-choice assignments")
        constraints = [
            models.UniqueConstraint(fields=["student", "sheet"], name="unique_student_sheet_assignment"),
        ]

    def __str__(self) -> str:
        return f"{self.student.username}: #{self.number} ({self.sheet})"


class MCSubmission(models.Model):
    """An immutable, timestamped set of answers by a student to one sheet."""

    sheet = models.ForeignKey(
        MCSheet,
        on_delete=models.PROTECT,
        related_name="submissions",
        help_text=_("Sheet this submission answers."),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mc_submissions",
        help_text=_("Student who made this submission."),
    )
    answers = models.JSONField(
        default=dict,
        help_text=_("Mapping of question id to selected option id."),
    )
    submission_number = models.PositiveSmallIntegerField(default=1)
    idempotency_key = models.CharField(max_length=128)
    score = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    ideal_score = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Multiple-choice submission")
        verbose_name_plural = _("Multiple-choice submissions")
        ordering = ["submitted_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "student", "idempotency_key"],
                name="unique_mc_idempotency_per_student_sheet",
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.id} {self.student.username} -> {self.sheet} ({self.submitted_at:%Y-%m-%d %H:%M}Z)"

    def per_question(self) -> list[dict]:
        """Return the correct/wrong breakdown per question for this submission."""
        answers = {int(k): v for k, v in (self.answers or {}).items()}
        out: list[dict] = []
        for question in self.questions():
            correct_option = question.correct_option()
            chosen = answers.get(question.id)
            is_correct = correct_option is not None and chosen == correct_option.id
            out.append(
                {
                    "question_id": question.id,
                    "selected_option_id": chosen,
                    "correct_option_id": correct_option.id if correct_option else None,
                    "is_correct": is_correct,
                }
            )
        return out

    def questions(self) -> list[MCQuestion]:
        """The sheet's card questions in order."""
        return self.sheet.questions()
