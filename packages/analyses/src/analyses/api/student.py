"""
Student-facing analysis endpoints.

All endpoints enforce that a student can only see and submit their own
analysis instances (via their ``StudentAssignment`` rows). The correct ion
set is never exposed before a submission exists.
"""

from __future__ import annotations

from analyses.api.schemas import (
    AnalysisDetailOut,
    AnalysisSummary,
    SubmissionIn,
    SubmissionOut,
    SummaryOut,
    ion_ids_to_dicts,
)
from analyses.models import AnalysisInstance
from ninja import Router
from ninja.errors import AuthenticationError, HttpError
from ninja.errors import ValidationError as NinjaValidationError
from substances.api.schemas import ion_to_schema

router = Router(tags=["analyses:student"])


def _owned_instance(request, instance_id: int) -> AnalysisInstance:
    """Fetch an analysis instance and ensure the requesting student owns it."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    instance = (
        AnalysisInstance.objects.filter(pk=instance_id, assignments__student=user)
        .prefetch_related("type", "type__possible_ions", "submissions", "submissions__selected_ions")
        .first()
    )
    if instance is None:
        # Deliberately indistinguishable from "not found"
        raise HttpError(404, "Analysis not found.")
    return instance


@router.get("/analyses", response=list[AnalysisSummary])
def list_my_analyses(request):
    """All analysis instances assigned to the current student."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    instances = AnalysisInstance.objects.for_student(user)
    return [AnalysisSummary.from_instance(i) for i in instances]


@router.get("/analyses/{analysis_id}", response=AnalysisDetailOut)
def analysis_detail(request, analysis_id: int):
    """Analysis details with the *possible* ion set (correct set hidden)."""
    instance = _owned_instance(request, analysis_id)
    type_ = instance.type
    possible = list(type_.possible_ions.all())
    cations = [ion_to_schema(i) for i in possible if i.kind == "cation"]
    anions = [ion_to_schema(i) for i in possible if i.kind == "anion"]
    return {
        "id": instance.id,
        "type": type_.name,
        "type_description": type_.description,
        "number": instance.number,
        "window_status": instance.window_status(),
        "window_start": instance.window_start.isoformat(),
        "window_end": instance.window_end.isoformat(),
        "submission_count": instance.submission_count(),
        "submission_limit": instance.submission_limit(),
        "cations": cations,
        "anions": anions,
    }


@router.get("/analyses/{analysis_id}/substances", response=list[dict])
def analysis_substances(request, analysis_id: int):
    """Reference substances related to the analysis (by possible ions)."""
    instance = _owned_instance(request, analysis_id)
    from substances.models import Substance

    possible_ids = list(instance.type.possible_ions.values_list("id", flat=True))
    substances = (
        Substance.objects.filter(ions__id__in=possible_ids).distinct().prefetch_related("ions")
        if possible_ids
        else Substance.objects.none()
    )
    from substances.api.schemas import substance_to_schema

    return [substance_to_schema(s) for s in substances]


@router.get("/analyses/{analysis_id}/submissions", response=list[SubmissionOut])
def my_submissions(request, analysis_id: int):
    """The student's own submission history for this analysis."""
    instance = _owned_instance(request, analysis_id)
    subs = instance.submissions.filter(student=request.user).order_by("submitted_at", "id")
    return [
        {
            "id": s.id,
            "submission_number": s.submission_number,
            "score": s.score,
            "correct_count": s.correct_count,
            "wrong_count": s.wrong_count,
            "missing_count": s.missing_count,
            "penalty": s.penalty,
            "ideal_score": s.ideal_score,
            "submitted_at": s.submitted_at.isoformat(),
        }
        for s in subs
    ]


@router.post("/analyses/{analysis_id}/submissions", response=dict)
def create_submission(request, analysis_id: int, payload: SubmissionIn):
    """
    Submit an ion selection. Idempotent via ``idempotency_key``.

    Returns the graded submission plus the full result breakdown.
    """
    instance = _owned_instance(request, analysis_id)
    if not payload.confirmed:
        raise NinjaValidationError({"confirmed": ["You must confirm the selection before submitting."]})

    from django.core.exceptions import PermissionDenied as _PD
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        submission = instance.submit(
            request.user,
            payload.ion_ids,
            idempotency_key=payload.idempotency_key,
        )
    except _PD as exc:
        raise HttpError(403, str(exc)) from exc
    except DjangoValidationError as exc:
        if hasattr(exc, "error_dict"):
            detail = exc.error_dict
        elif hasattr(exc, "error_list"):
            detail = [str(e) for e in exc.error_list]
        else:
            detail = [str(exc)]
        raise HttpError(400, str(detail)) from exc

    return _submission_result_payload(instance, submission)


def _submission_result_payload(instance: AnalysisInstance, submission) -> dict:
    """Assemble the response body for a (just created) submission."""
    breakdown = submission.ion_breakdown()
    return {
        "submission": {
            "id": submission.id,
            "submission_number": submission.submission_number,
            "score": submission.score,
            "correct_count": submission.correct_count,
            "wrong_count": submission.wrong_count,
            "missing_count": submission.missing_count,
            "penalty": submission.penalty,
            "ideal_score": submission.ideal_score,
            "submitted_at": submission.submitted_at.isoformat(),
        },
        "result": {
            "correct_ions": ion_ids_to_dicts(breakdown["correct"]),
            "wrong_ions": ion_ids_to_dicts(breakdown["wrong"]),
            "missing_ions": ion_ids_to_dicts(breakdown["missing"]),
            "total_score": instance.score(),
            "ideal_score": instance.ideal_score(),
        },
    }


@router.get("/analyses/{analysis_id}/result", response=dict)
def analysis_result(request, analysis_id: int):
    """The control-query result; only available after a submission exists."""
    instance = _owned_instance(request, analysis_id)
    submissions = instance.submissions.filter(student=request.user).order_by("submitted_at", "id")
    if not submissions:
        raise HttpError(404, "No submissions yet – the result is not available.")
    subs_out: list[dict] = []
    for s in submissions:
        breakdown = s.ion_breakdown()
        subs_out.append(
            {
                "id": s.id,
                "submission_number": s.submission_number,
                "submitted_at": s.submitted_at.isoformat(),
                "score": s.score,
                "penalty": s.penalty,
                "ideal_score": s.ideal_score,
                "correct_ions": ion_ids_to_dicts(breakdown["correct"]),
                "wrong_ions": ion_ids_to_dicts(breakdown["wrong"]),
                "missing_ions": ion_ids_to_dicts(breakdown["missing"]),
            }
        )
    return {
        "analysis_id": instance.id,
        "submissions": subs_out,
        "total_score": instance.score(),
        "ideal_score": instance.ideal_score(),
    }


@router.get("/me/summary", response=SummaryOut)
def my_summary(request):
    """All assigned analyses with scores and the total/ideal points."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    instances = AnalysisInstance.objects.for_student(user)
    analyses = [AnalysisSummary.from_instance(i) for i in instances]
    total = sum(a.score or 0 for a in analyses)
    ideal = sum(i.ideal_score() for i in instances)
    return {"total_score": total, "ideal_score": ideal, "analyses": analyses}
