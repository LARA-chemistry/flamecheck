"""
Service helpers for the analyses app that are not tied to a single model method.

Currently provides the *random substance assignment* used by the admin to give
each student in a course a different, random analysis composition for an
announcement: a random subset of the analysis type's possible ions becomes the
per-student answer key (``correct_ions``), and the substances consistent with
that composition are recorded on the instance as ``assigned_substances``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from config.models import Course
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from substances.models import Ion, Substance

from .models import AnalysisInstance


class InsufficientIonsError(Exception):
    """Raised when a type's possible-ion set is too small to randomize."""


@dataclass(frozen=True)
class StudentAssignmentResult:
    """Per-student outcome of a randomize run."""

    student_id: int
    student_name: str
    instance_id: int
    correct_ion_ids: list[int]
    assigned_substance_ids: list[int]


def _pick_random_ion_subset(
    possible_ions: list[Ion],
    min_ions: int,
    max_ions: int,
    rng: random.Random,
) -> list[int]:
    """
    Pick a random subset of ``possible_ions`` with size in ``[min_ions, max_ions]``.

    When the set contains both cations and anions (and there is room), the pick
    guarantees at least one of each kind so a composition is chemically sensible.
    The returned ids are ordered cations-first for stable display.
    """
    cations = [i for i in possible_ions if i.kind == Ion.Kind.CATION]
    anions = [i for i in possible_ions if i.kind == Ion.Kind.ANION]
    size = rng.randint(min_ions, max_ions)
    size = max(1, min(size, len(possible_ions)))

    chosen: list[Ion] = []
    # Reserve one of each kind when feasible, then fill the remainder randomly.
    reserve: list[Ion] = []
    if size >= 2 and cations and anions:
        reserve = [rng.choice(cations), rng.choice(anions)]
        remaining = size - len(reserve)
    else:
        remaining = size

    pool = [i for i in possible_ions if i not in reserve]
    fill_count = min(remaining, len(pool))
    chosen = reserve + rng.sample(pool, fill_count)
    # De-duplicate defensively (sample never repeats, but reserve could overlap if
    # a kind has a single member and the pool excluded it).
    seen: set[int] = set()
    unique: list[Ion] = []
    for ion in chosen:
        if ion.id not in seen:
            seen.add(ion.id)
            unique.append(ion)
    if len(unique) < size:
        # Top up from the pool if dedup shrunk the set.
        for ion in pool:
            if len(unique) >= size:
                break
            if ion.id not in seen:
                seen.add(ion.id)
                unique.append(ion)
    unique.sort(key=lambda i: (i.kind != Ion.Kind.CATION, i.symbol))
    return [i.id for i in unique]


def _substances_for_correct_ions(correct_ids: list[int]) -> list[Substance]:
    """Substances sharing at least one of the correct ions (prep convention)."""
    if not correct_ids:
        return []
    return list(Substance.objects.filter(ions__id__in=correct_ids).distinct().prefetch_related("ions"))


def randomize_substances_for_announcement(
    course: Course,
    number: int,
    *,
    min_ions: int = 3,
    max_ions: int = 5,
    rng: random.Random | None = None,
) -> list[StudentAssignmentResult]:
    """
    Randomize the substance assignment for every student in ``course``/``number``.

    Each student's :class:`AnalysisInstance` gets a fresh random subset of the
    analysis type's possible ions as its ``correct_ions`` (the answer key), and
    the matching substances are stored on ``assigned_substances``. Runs in a
    single transaction.

    Args:
        course: The course whose announcement is being randomized.
        number: The announcement number within the course.
        min_ions: Minimum number of ions to pick per student.
        max_ions: Maximum number of ions to pick per student.
        rng: Optional seeded :class:`random.Random` (for tests).

    Returns:
        One :class:`StudentAssignmentResult` per randomized student instance.

    Raises:
        InsufficientIonsError: If the analysis type has fewer possible ions than
            ``max(min_ions, 1)``.

    """
    if min_ions > max_ions:
        min_ions, max_ions = max_ions, min_ions
    min_ions = max(1, min_ions)
    max_ions = max(min_ions, max_ions)
    rng = rng or random.Random()

    instances = list(
        AnalysisInstance.objects.filter(course=course, number=number)
        .select_related("type")
        .prefetch_related("type__possible_ions")
        .order_by("id")
    )
    if not instances:
        return []

    results: list[StudentAssignmentResult] = []
    with transaction.atomic():
        for instance in instances:
            possible = list(instance.type.possible_ions.all())
            if len(possible) < min_ions:
                raise InsufficientIonsError(
                    _(
                        f"Analysis type '{instance.type.name}' has only {len(possible)} possible "
                        f"ions; at least {min_ions} are required to randomize."
                    )
                )
            correct_ids = _pick_random_ion_subset(possible, min_ions, max_ions, rng)
            instance.correct_ions.set(correct_ids)
            substances = _substances_for_correct_ions(correct_ids)
            instance.assigned_substances.set([s.id for s in substances])
            student = instance.assignments.select_related("student").first()
            results.append(
                StudentAssignmentResult(
                    student_id=student.student_id if student else 0,
                    student_name=(student.student.name or student.student.username) if student else "",
                    instance_id=instance.id,
                    correct_ion_ids=correct_ids,
                    assigned_substance_ids=[s.id for s in substances],
                )
            )
    return results
