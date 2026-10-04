"""
Factory-boy definitions for the ``multichoice`` app models.

``MCQuestion`` owns its options (built with ``post_generation``), ``MCCard``
owns its ordered question links, and ``MCSheet`` carries a submission window
(open / too-early / too-late via ``_window``) plus student assignments.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from factory import Sequence, SubFactory, post_generation
from factory.django import DjangoModelFactory

from .models import MCCard, MCCardQuestion, MCOption, MCQuestion, MCSheet, MCStudentAssignment

_OPEN_DELTA = timedelta(hours=1)


def _window(state: str) -> tuple:
    """Return ``(window_start, window_end)`` for a window in ``state`` vs now."""
    now = timezone.now().replace(microsecond=0)
    if state == "open":
        start, end = now - _OPEN_DELTA, now + _OPEN_DELTA
    elif state == "too_early":
        start, end = now + _OPEN_DELTA, now + timedelta(hours=2)
    else:  # too_late
        start, end = now - timedelta(hours=2), now - _OPEN_DELTA
    return start, end


class MCQuestionFactory(DjangoModelFactory):
    """Factory for :class:`multichoice.models.MCQuestion` (with two options)."""

    class Meta:
        """Meta options for :class:`MCQuestionFactory`."""

        model = MCQuestion

    course = SubFactory("config.factory.CourseFactory")
    text = Sequence(lambda n: f"Question {n}?")
    description = ""
    remarks = ""

    @post_generation
    def options(self, create, extracted, **kwargs):
        """Create two options (first correct) unless options are supplied."""
        if not create:
            return
        opts = extracted or [
            {"text": "Correct answer", "is_correct": True, "sort_order": 0},
            {"text": "Wrong answer", "is_correct": False, "sort_order": 1},
        ]
        for i, o in enumerate(opts):
            MCOption.objects.create(
                question=self,
                text=o.get("text", f"Option {i}"),
                is_correct=o.get("is_correct", i == 0),
                sort_order=o.get("sort_order", i),
            )


class MCCardFactory(DjangoModelFactory):
    """Factory for :class:`multichoice.models.MCCard` (with one question)."""

    class Meta:
        """Meta options for :class:`MCCardFactory`."""

        model = MCCard

    course = SubFactory("config.factory.CourseFactory")
    title = Sequence(lambda n: f"Card {n}")
    description = ""
    remarks = ""

    @post_generation
    def questions(self, create, extracted, **kwargs):
        """Link the given question(s), or a fresh default question."""
        if not create:
            return
        qs = extracted or [MCQuestionFactory(course=self.course)]
        for i, q in enumerate(qs):
            MCCardQuestion.objects.create(card=self, question=q, order=i)


class MCSheetFactory(DjangoModelFactory):
    """Factory for :class:`multichoice.models.MCSheet` (open window by default)."""

    class Meta:
        """Meta options for :class:`MCSheetFactory`."""

        model = MCSheet

    card = SubFactory(MCCardFactory)
    course = SubFactory("config.factory.CourseFactory")
    window_start = _window("open")[0]
    window_end = _window("open")[1]
    number = 1


class MCStudentAssignmentFactory(DjangoModelFactory):
    """Factory for :class:`multichoice.models.MCStudentAssignment`."""

    class Meta:
        """Meta options for :class:`MCStudentAssignmentFactory`."""

        model = MCStudentAssignment

    course = SubFactory("config.factory.CourseFactory")
    sheet = SubFactory(MCSheetFactory)
    student = SubFactory("users.factory.UserFactory")
    number = 1


def create_mc_demo(course, *, questions=3, cards=2, window_state: str = "open"):
    """
    Build a small, self-consistent MC demo set for ``course``.

    Creates ``questions`` questions (grouped into up to ``cards`` cards of
    <= 3 questions each) and one open sheet per card, returning
    ``(questions, cards, sheets)``.
    """
    start, end = _window(window_state)
    made_questions = [MCQuestionFactory(course=course) for _ in range(questions)]
    made_cards: list[MCCard] = []
    for c in range(cards):
        chunk = made_questions[c::cards]
        if not chunk:
            continue
        card = MCCardFactory(course=course, questions=chunk[:3])
        MCSheetFactory(card=card, course=course, window_start=start, window_end=end, number=c + 1)
        made_cards.append(card)
    sheets = MCSheet.objects.filter(card__in=made_cards, course=course)
    return made_questions, made_cards, list(sheets)
