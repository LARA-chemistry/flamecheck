"""
Service for the "new analysis" submission mode.

In this mode a *wrong* submission (selected ion set differs from the answer key)
hands the student a fresh, randomly composed analysis of the same type instead of
merely allowing another submission on the same sheet. The new analysis is bounded
by the analysis type's ``max_repetitions`` and raises an
:class:`~analyses.models.AnalysisNotification` so the course's assistants are told
a re-trial was created.
"""

from __future__ import annotations

import random

from django.db import transaction
from users.models import StudentAssignment

from analyses.models import AnalysisInstance, AnalysisNotification
from analyses.services.randomize import _pick_random_ion_subset, _substances_for_correct_ions


def maybe_generate_retry(instance: AnalysisInstance, student, submission) -> AnalysisInstance | None:
    """
    Generate a re-trial analysis after ``submission`` if the mode and limits allow it.

    A re-trial is created only when all of the following hold:

    * the applicable grading configuration uses the ``new_analysis`` submission
      mode,
    * ``submission`` is *wrong* — its selected ion set differs from the instance's
      answer key,
    * the student has not yet exhausted the analysis type's ``max_repetitions``
      for this (course, announcement number).

    The new instance is a fresh random composition of the same type (a random
    subset of its possible ions), inherits the current instance's submission
    window and announcement number, is assigned to the student, and raises an
    :class:`~analyses.models.AnalysisNotification`. It remains fully editable by
    the admin through the usual instance-editing endpoint.

    Args:
        instance: The analysis the student just submitted to.
        student: The requesting student user.
        submission: The :class:`~analyses.models.Submission` just recorded.

    Returns:
        The newly generated :class:`AnalysisInstance`, or ``None`` when no
        re-trial applies (mode off, correct submission, or re-trials exhausted).

    """
    grading = instance.grading_config()
    if grading.submission_mode != "new_analysis":
        return None

    selected = set(submission.selected_ions.values_list("id", flat=True))
    correct = set(instance.correct_ions.values_list("id", flat=True))
    if selected == correct:
        return None  # Correct submission: nothing to re-trial.

    analysis_type = instance.type
    max_instances = 1 + int(analysis_type.max_repetitions)
    existing = (
        AnalysisInstance.objects.filter(
            course=instance.course,
            number=instance.number,
            assignments__student=student,
        )
        .distinct()
        .count()
    )
    if existing >= max_instances:
        return None  # Re-trials exhausted for this announcement.

    possible = list(analysis_type.possible_ions.all())
    if not possible:
        return None  # Nothing to randomize over.

    with transaction.atomic():
        correct_ids = _pick_random_ion_subset(possible, 3, 5, random.Random())
        new_instance = AnalysisInstance.objects.create(
            type=analysis_type,
            course=instance.course,
            number=instance.number,
            window_start=instance.window_start,
            window_end=instance.window_end,
        )
        new_instance.correct_ions.set(correct_ids)
        new_instance.assigned_substances.set([s.id for s in _substances_for_correct_ions(correct_ids)])
        StudentAssignment.objects.create(
            course=instance.course,
            student=student,
            instance=new_instance,
            number=instance.number,
        )
        AnalysisNotification.objects.create(course=instance.course, instance=new_instance, student=student)
    return new_instance
