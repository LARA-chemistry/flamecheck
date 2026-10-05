"""
Student-facing multiple-choice endpoints.

All endpoints enforce that a student only sees and submits their own sheets
(via ``MCStudentAssignment``). The correct answers are never exposed before a
submission exists.
"""

from __future__ import annotations

from config.services.notifications import notify_submission
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import Router
from ninja.errors import AuthenticationError, HttpError
from ninja.errors import ValidationError as NinjaValidationError

from multichoice.api.schemas import MCSheetSummary, MCSubmissionIn
from multichoice.models import MCSheet

router = Router(tags=["multichoice:student"])


def _authed_student(request):
    """Return the authenticated user or raise 401."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    return user


def _owned_sheet(request, sheet_id: int) -> MCSheet:
    """Fetch a sheet and ensure the requesting student is assigned to it."""
    user = _authed_student(request)
    sheet = (
        MCSheet.objects.filter(pk=sheet_id, assignments__student=user)
        .select_related("card")
        .prefetch_related("card__card_questions__question__options_set", "submissions")
        .first()
    )
    if sheet is None:
        # Deliberately indistinguishable from "not found".
        raise HttpError(404, "Card not found.")
    return sheet


@router.get("/mc-sheets", response=list[MCSheetSummary])
def list_my_mc_sheets(request):
    """All multiple-choice sheets assigned to the current student."""
    user = _authed_student(request)
    sheets = MCSheet.objects.for_student(user)
    return [
        {
            "id": s.id,
            "card_title": s.card.title,
            "number": s.number,
            "window_status": s.window_status(),
            "window_start": s.window_start.isoformat(),
            "window_end": s.window_end.isoformat(),
            "submission_count": s.submissions.filter(student=user).count(),
            "score": s.score(),
            "question_count": s.card.question_count(),
        }
        for s in sheets
    ]


@router.get("/mc-sheets/{sheet_id}", response=dict)
def mc_sheet_detail(request, sheet_id: int):
    """
    Return a sheet's card and questions.

    Correct answers are hidden until a submission exists, in which case the
    graded result is included.
    """
    sheet = _owned_sheet(request, sheet_id)
    user = request.user
    card = sheet.card
    submission = sheet.submissions.filter(student=user).order_by("submitted_at", "id").first()
    if submission is None:
        questions = [q.public_payload() for q in card.questions()]
        result = None
    else:
        questions = [q.result_payload() for q in card.questions()]
        result = {
            "score": submission.score,
            "ideal_score": submission.ideal_score,
            "correct_count": submission.correct_count,
            "wrong_count": submission.wrong_count,
            "per_question": submission.per_question(),
            "submitted_at": submission.submitted_at.isoformat(),
        }
    return {
        "id": sheet.id,
        "card_title": card.title,
        "number": sheet.number,
        "window_status": sheet.window_status(),
        "window_start": sheet.window_start.isoformat(),
        "window_end": sheet.window_end.isoformat(),
        "questions": questions,
        "result": result,
    }


@router.post("/mc-sheets/{sheet_id}/submissions", response=dict)
def create_mc_submission(request, sheet_id: int, payload: MCSubmissionIn):
    """
    Submit the answers to a sheet (question id -> option id).

    Idempotent via ``idempotency_key``: a retried submission with the same key
    returns the stored result instead of a new submission.
    """
    sheet = _owned_sheet(request, sheet_id)
    user = request.user
    # JSON object keys are strings; the model expects integer question ids.
    answers = {int(k): int(v) for k, v in payload.answers.items()}
    try:
        submission = sheet.submit(user, answers, idempotency_key=payload.idempotency_key)
    except PermissionDenied as exc:
        raise HttpError(403, "You are not assigned to this card.") from exc
    except DjangoValidationError as exc:
        messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
        raise NinjaValidationError({"answers": list(messages)}) from exc

    # Optionally notify the student / assistants (PGP e-mail), same gating as
    # the analysis submissions.
    notify_submission(
        course=sheet.course,
        student=user,
        analysis_name=sheet.card.title,
        score=submission.score,
        ideal_score=submission.ideal_score,
        submission_number=getattr(submission, "submission_number", 1),
        submission_kind="mc",
    )
    return {
        "id": submission.id,
        "score": submission.score,
        "correct_count": submission.correct_count,
        "wrong_count": submission.wrong_count,
        "ideal_score": submission.ideal_score,
        "submitted_at": submission.submitted_at.isoformat(),
    }


@router.get("/mc-sheets/{sheet_id}/result", response=dict)
def mc_sheet_result(request, sheet_id: int):
    """The result of the student's first submission (correct/wrong per question)."""
    sheet = _owned_sheet(request, sheet_id)
    user = request.user
    submission = sheet.submissions.filter(student=user).order_by("submitted_at", "id").first()
    if submission is None:
        raise HttpError(404, "No submission yet.")
    return {
        "score": submission.score,
        "ideal_score": submission.ideal_score,
        "correct_count": submission.correct_count,
        "wrong_count": submission.wrong_count,
        "per_question": submission.per_question(),
        "submitted_at": submission.submitted_at.isoformat(),
    }
