"""
Factory-boy definitions for the ``config`` app models.

``Course`` is a normal record. ``GradingConfig`` and ``AppSettings`` are
**singletons** (``pk=1``), so their factories pin ``pk=1`` and use
``django_get_or_create`` to be idempotent — calling the factory twice returns the
same row instead of raising. ``AssistantCourse`` links an assistant to a course
with a unique constraint, so it uses ``SubFactory`` for both ends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from factory import Faker, Sequence, SubFactory, post_generation
from factory.django import DjangoModelFactory

from .models import AppSettings, AssistantCourse, Course, GradingConfig

if TYPE_CHECKING:
    pass


class CourseFactory(DjangoModelFactory):
    """Factory for :class:`config.models.Course`."""

    class Meta:
        """Meta options for :class:`CourseFactory`."""

        model = Course
        django_get_or_create = ("name",)

    name = Sequence(lambda n: f"Inorganic Chemistry WS 20{n % 100}")
    semester = Faker("bothify", text="WS 20##")
    track = Faker("random_element", elements=["biology", "pharmacy", "materials", ""])
    is_active = True


class GradingConfigFactory(DjangoModelFactory):
    """Factory for the singleton :class:`config.models.GradingConfig` (``pk=1``)."""

    class Meta:
        """Meta options for :class:`GradingConfigFactory`."""

        model = GradingConfig
        django_get_or_create = ("pk",)

    pk = 1
    points_per_correct_ion = 10
    penalty_second_submission = 2
    penalty_third_submission = 4
    false_positive_deduction = 0
    grading_mode = "per_ion"
    max_submissions_per_analysis = 3
    final_score_strategy = "best"

    # Alternate scoring modes are just field overrides, e.g.:
    #   GradingConfigFactory(grading_mode="per_analysis")
    #   GradingConfigFactory(max_submissions_per_analysis=1, false_positive_deduction=2)
    #   GradingConfigFactory(final_score_strategy="last")


class AssistantCourseFactory(DjangoModelFactory):
    """Factory for :class:`config.models.AssistantCourse`."""

    class Meta:
        """Meta options for :class:`AssistantCourseFactory`."""

        model = AssistantCourse
        django_get_or_create = ("assistant", "course")

    assistant = SubFactory("users.factory.AssistantUserFactory")
    course = SubFactory(CourseFactory)


class AppSettingsFactory(DjangoModelFactory):
    """Factory for the singleton :class:`config.models.AppSettings` (``pk=1``)."""

    class Meta:
        """Meta options for :class:`AppSettingsFactory`."""

        model = AppSettings
        django_get_or_create = ("pk",)

    pk = 1
    points_per_analysis = 10
    analyses_per_course = 3

    @post_generation
    def active_course(obj, create, extracted, **kwargs):
        """Optionally point the settings at a course."""
        if not create:
            return
        if extracted is None:
            return
        obj.active_course = extracted
        obj.save()
