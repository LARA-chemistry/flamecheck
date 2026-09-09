"""
Factory-boy definitions for the ``analyses`` app models.

``AnalysisType`` carries the *possible* ion set (M2M, handled with
``post_generation``). ``AnalysisInstance`` carries the *correct* ion set (the
answer key) plus a submission time window; the window is built from Faker
datetimes and can be overridden to an open / closed window via Traits and
``SubFactory`` arguments. ``Submission`` is immutable and idempotent — the
``idempotency_key`` is a fresh UUID per instance so batches never collide, and
the selected ions are attached with ``post_generation``.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.utils import timezone

from factory import Faker, LazyFunction, post_generation, Sequence, SubFactory
from factory.django import DjangoModelFactory

from .models import AnalysisInstance, AnalysisType, Submission

# A window that is comfortably open "now": started an hour ago, ends in an hour.
_OPEN_DELTA = timedelta(hours=1)


def _window(state: str) -> tuple:
    """Return ``(window_start, window_end)`` for a window in ``state`` vs "now"."""
    now = timezone.now().replace(microsecond=0)
    if state == "open":
        return now - _OPEN_DELTA, now + _OPEN_DELTA
    if state == "too_early":
        return now + _OPEN_DELTA, now + timedelta(hours=2)
    if state == "too_late":
        return now - timedelta(hours=2), now - _OPEN_DELTA
    raise ValueError(f"Unknown window state: {state!r}")


class AnalysisTypeFactory(DjangoModelFactory):
    """Factory for :class:`analyses.models.AnalysisType`."""

    class Meta:
        model = AnalysisType
        django_get_or_create = ("name",)

    name = Sequence(lambda n: f"Analysis {n}")
    description = Faker("sentence")
    created_at = Faker("date_time_this_year", before_now=True)

    @post_generation
    def possible_ions(obj, create, extracted, **kwargs):
        """Optionally attach the possible ion set (the ions shown to students)."""
        if not create:
            return
        if extracted is None:
            return
        if isinstance(extracted, list):
            obj.possible_ions.set(extracted)
        else:
            obj.possible_ions.add(extracted)


class AnalysisInstanceFactory(DjangoModelFactory):
    """Factory for :class:`analyses.models.AnalysisInstance`."""

    class Meta:
        model = AnalysisInstance

    type = SubFactory(AnalysisTypeFactory)
    course = SubFactory("config.factory.CourseFactory")
    number = Faker("pyint", min_value=1, max_value=4)
    # Default to a window that is open "now" (see :meth:`window_kwargs`).
    window_start = LazyFunction(lambda: _window("open")[0])
    window_end = LazyFunction(lambda: _window("open")[1])
    created_at = Faker("date_time_this_year", before_now=True)

    @classmethod
    def make(cls, window: str = "open", **overrides) -> "AnalysisInstance":
        """
        Build an instance whose window is in a given state relative to "now".

        Args:
            window: One of ``'open'`` (default), ``'too_early'`` or ``'too_late'``.
            **overrides: Any other field overrides.

        Returns:
            AnalysisInstance: The created instance.

        """
        start, end = _window(window)
        return cls.create(window_start=start, window_end=end, **overrides)

    @post_generation
    def correct_ions(obj, create, extracted, **kwargs):
        """Optionally attach the correct (answer-key) ion set."""
        if not create:
            return
        if extracted is None:
            return
        if isinstance(extracted, list):
            obj.correct_ions.set(extracted)
        else:
            obj.correct_ions.add(extracted)


class SubmissionFactory(DjangoModelFactory):
    """Factory for the immutable :class:`analyses.models.Submission`."""

    class Meta:
        model = Submission
        # Idempotency key is unique per (instance, student), so generate a
        # fresh UUID for each submission to keep batches collision-free.
        exclude = ("idempotency_key",)

    analysis_instance = SubFactory(AnalysisInstanceFactory)
    student = SubFactory("users.factory.UserFactory")
    submission_number = 1
    idempotency_key = LazyFunction(lambda: uuid.uuid4().hex)
    score = 0
    correct_count = 0
    wrong_count = 0
    missing_count = 0
    penalty = 0
    ideal_score = 10
    submitted_at = Faker("date_time_this_year", before_now=True)

    @post_generation
    def selected_ions(obj, create, extracted, **kwargs):
        """Optionally attach the ions the student selected."""
        if not create:
            return
        if extracted is None:
            return
        if isinstance(extracted, list):
            obj.selected_ions.set(extracted)
        else:
            obj.selected_ions.add(extracted)
