"""
Service for generating a newly-enrolled student's course analyses.

When a student completes onboarding (the OAuth flow), the system enrols them in
a course and creates their personal analysis instances: one per announcement,
with a *randomized* composition (a random subset of the type's possible ions as
the answer key) and the matching reference substances. The count follows the
course settings (:data:`~config.models.AppSettings.analyses_per_course`).
"""

from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from analyses.models import AnalysisInstance, AnalysisType
from analyses.services.randomize import _pick_random_ion_subset, _substances_for_correct_ions

if TYPE_CHECKING:
    from config.models import Course
    from users.models import User


class NoAnalysisTypeError(Exception):
    """Raised when no analysis type is available to generate instances from."""


# Composition size bounds (mirrors the admin randomize defaults) and how long a
# freshly generated window stays open.
MIN_IONS = 3
MAX_IONS = 5
ONBOARDING_WINDOW_DAYS = 14


def generate_course_analyses(
    student: User,
    course: Course,
    *,
    analyses_count: int | None = None,
    rng: random.Random | None = None,
) -> list[AnalysisInstance]:
    """
    Create and assign this student's analyses for ``course``.

    For each announcement number ``1..analyses_count`` (default: the course
    setting ``analyses_per_course``) an :class:`AnalysisInstance` is created with
    a random composition drawn from the chosen analysis type's possible ions, and
    a :class:`~users.models.StudentAssignment` links it to ``student``. Numbers
    already assigned to the student in this course are skipped (idempotent).

    Args:
        student: The student to enrol.
        course: The course the analyses belong to.
        analyses_count: How many analyses to generate (defaults to the course
            setting). ``0`` creates nothing.
        rng: Optional seeded :class:`random.Random` (for tests).

    Returns:
        The newly created :class:`AnalysisInstance` objects (one per generated
        announcement).

    Raises:
        NoAnalysisTypeError: If no analysis type with possible ions exists.

    """
    if analyses_count is None:
        from config.models import AppSettings

        s = AppSettings.objects.first()
        analyses_count = int(s.analyses_per_course) if s is not None else 3
    analyses_count = max(0, int(analyses_count))
    if analyses_count == 0:
        return []

    rng = rng or random.Random()

    # Prefer types with a rich enough possible-ion set for a sensible
    # composition; fall back to any type that has at least one possible ion.
    types = list(AnalysisType.objects.all())
    with_ions = [(t, list(t.possible_ions.all())) for t in types if t.possible_ions.exists()]
    pool = [(t, p) for (t, p) in with_ions if len(p) >= MIN_IONS] or with_ions
    if not pool:
        raise NoAnalysisTypeError("No analysis type with possible ions is defined; cannot generate analyses.")

    now = timezone.now()
    window_start = now - timedelta(minutes=1)  # open immediately
    window_end = now + timedelta(days=ONBOARDING_WINDOW_DAYS)

    created: list[AnalysisInstance] = []
    with transaction.atomic():
        for number in range(1, analyses_count + 1):
            if student.analysis_assignments.filter(course=course, number=number).exists():
                continue
            analysis_type, possible = pool[(number - 1) % len(pool)]
            instance = AnalysisInstance.objects.create(
                type=analysis_type,
                course=course,
                number=number,
                window_start=window_start,
                window_end=window_end,
            )
            correct_ids = _pick_random_ion_subset(possible, MIN_IONS, MAX_IONS, rng)
            instance.correct_ions.set(correct_ids)
            instance.assigned_substances.set([s.id for s in _substances_for_correct_ions(correct_ids)])
            from users.models import StudentAssignment

            StudentAssignment.objects.create(student=student, instance=instance, course=course, number=number)
            created.append(instance)
    return created
