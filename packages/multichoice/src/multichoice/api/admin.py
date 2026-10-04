"""
Admin endpoints for the multiple-choice designer.

CRUD for questions, cards and time-windowed sheets, all admin-only and logged
to the audit logger. Grading (points-per-card / per-wrong-answer penalty) is
configured per course through the existing grading-config endpoints.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from config.models import Course
from ninja import Router
from ninja.errors import HttpError, ValidationError
from users.models import User

from multichoice.api.schemas import MCCardIn, MCQuestionIn, MCSheetIn
from multichoice.models import (
    MAX_QUESTIONS_PER_CARD,
    MCCard,
    MCCardQuestion,
    MCOption,
    MCQuestion,
    MCSheet,
    MCStudentAssignment,
    MCSubmission,
)

logger = logging.getLogger("flamecheck.audit")

router = Router(tags=["multichoice:admin"])


def _admin_user(request) -> User:
    """Return the request user if admin, else raise 401/403."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise HttpError(401, "Authentication required.")
    if not user.is_admin:
        raise HttpError(403, "Admin role required.")
    return user


def _parse_dt(value: str) -> datetime:
    """Parse an ISO-8601 datetime (with or without a trailing Z)."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(UTC)


def _question_in_use(question: MCQuestion) -> bool:
    """True when any submission answers this question (options must stay stable)."""
    return MCSubmission.objects.filter(sheet__card__card_questions__question=question).exists()


# ---- questions -----------------------------------------------------------------
def _question_payload(q: MCQuestion) -> dict:
    """Serialize a question for the admin (with the correct-option flag)."""
    return {
        "id": q.id,
        "text": q.text,
        "description": q.description,
        "remarks": q.remarks,
        "options": [
            {"id": o.id, "text": o.text, "is_correct": o.is_correct, "sort_order": o.sort_order} for o in q.options()
        ],
        "card_count": q.card_links.count(),
    }


def _validate_options(options: list[MCQuestionIn]) -> None:
    """At least two options and exactly one marked correct."""
    if len(options) < 2:
        raise ValidationError({"options": ["A question needs at least two options."]})
    if sum(1 for o in options if o.is_correct) != 1:
        raise ValidationError({"options": ["Exactly one option must be marked correct."]})


def _replace_options(question: MCQuestion, options: list) -> None:
    """Delete the question's options and recreate them from ``options``."""
    question.options_set.all().delete()
    for i, o in enumerate(options):
        MCOption.objects.create(
            question=question,
            text=o.text,
            is_correct=o.is_correct,
            sort_order=o.sort_order if o.sort_order else i,
        )


@router.get("/questions", response=list[dict])
def list_questions(request, course_id: int | None = None):
    """List questions (optionally filtered by course)."""
    _admin_user(request)
    qs = MCQuestion.objects.all().prefetch_related("options_set")
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    return [_question_payload(q) for q in qs]


@router.post("/questions", response=dict)
def create_question(request, payload: MCQuestionIn, course_id: int):
    """Create a question in a course (admin)."""
    _admin_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    if payload.options is None:
        raise ValidationError({"options": ["A question needs at least two options."]})
    _validate_options(payload.options)
    q = MCQuestion.objects.create(
        course=course,
        text=payload.text,
        description=payload.description or "",
        remarks=payload.remarks or "",
    )
    for i, o in enumerate(payload.options):
        MCOption.objects.create(
            question=q,
            text=o.text,
            is_correct=o.is_correct,
            sort_order=o.sort_order if o.sort_order else i,
        )
    logger.info("Admin %s created MC question %d in %s", request.user.username, q.id, course.name)
    return _question_payload(q)


@router.put("/questions/{question_id}", response=dict)
def update_question(request, question_id: int, payload: MCQuestionIn):
    """
    Update a question (admin).

    Text/description/remarks are always editable. Options can only be changed
    while the question is not yet in use (no submission answers it).
    """
    _admin_user(request)
    q = MCQuestion.objects.filter(pk=question_id).first()
    if q is None:
        raise HttpError(404, "Question not found.")
    q.text = payload.text
    if payload.description is not None:
        q.description = payload.description
    if payload.remarks is not None:
        q.remarks = payload.remarks
    q.save()
    if payload.options is not None:
        if _question_in_use(q):
            raise HttpError(409, "Question is in use; its options can no longer be changed.")
        _validate_options(payload.options)
        _replace_options(q, payload.options)
    logger.info("Admin %s updated MC question %d", request.user.username, question_id)
    return _question_payload(q)


@router.delete("/questions/{question_id}", response=None)
def delete_question(request, question_id: int):
    """Delete a question that is not used by any card (admin)."""
    _admin_user(request)
    q = MCQuestion.objects.filter(pk=question_id).first()
    if q is None:
        raise HttpError(404, "Question not found.")
    if q.card_links.exists():
        raise HttpError(409, "Question is used by a card and cannot be deleted.")
    q.delete()
    logger.info("Admin %s deleted MC question %d", request.user.username, question_id)


# ---- cards ----------------------------------------------------------------------
def _card_payload(card: MCCard) -> dict:
    """Serialize a card for the admin (ordered questions)."""
    return {
        "id": card.id,
        "title": card.title,
        "description": card.description,
        "remarks": card.remarks,
        "questions": [{"id": q.id, "text": q.text} for q in card.questions()],
        "sheet_count": card.sheets.count(),
    }


@router.get("/cards", response=list[dict])
def list_cards(request, course_id: int | None = None):
    """List cards (optionally filtered by course)."""
    _admin_user(request)
    qs = MCCard.objects.all().prefetch_related("card_questions__question")
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    return [_card_payload(c) for c in qs]


@router.post("/cards", response=dict)
def create_card(request, payload: MCCardIn, course_id: int):
    """Create a card with 1..3 questions (admin)."""
    _admin_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    if not 1 <= len(payload.question_ids) <= MAX_QUESTIONS_PER_CARD:
        raise ValidationError({"question_ids": [f"A card holds 1 to {MAX_QUESTIONS_PER_CARD} questions."]})
    if len(set(payload.question_ids)) != len(payload.question_ids):
        raise ValidationError({"question_ids": ["Duplicate question in the card."]})
    questions = MCQuestion.objects.filter(id__in=payload.question_ids, course=course)
    if questions.count() != len(payload.question_ids):
        raise ValidationError({"question_ids": ["A question does not belong to this course."]})
    card = MCCard.objects.create(
        course=course,
        title=payload.title,
        description=payload.description or "",
        remarks=payload.remarks or "",
    )
    for i, qid in enumerate(payload.question_ids):
        MCCardQuestion.objects.create(card=card, question_id=qid, order=i)
    logger.info("Admin %s created MC card %d in %s", request.user.username, card.id, course.name)
    return _card_payload(card)


@router.put("/cards/{card_id}", response=dict)
def update_card(request, card_id: int, payload: MCCardIn):
    """
    Update a card (admin).

    Title/description/remarks are always editable. The question set can only be
    changed while the card has no sheets.
    """
    _admin_user(request)
    card = MCCard.objects.filter(pk=card_id).first()
    if card is None:
        raise HttpError(404, "Card not found.")
    card.title = payload.title
    if payload.description is not None:
        card.description = payload.description
    if payload.remarks is not None:
        card.remarks = payload.remarks
    card.save()
    if payload.question_ids is not None:
        if card.sheets.exists():
            raise HttpError(409, "Card has sheets; its questions can no longer be changed.")
        if not 1 <= len(payload.question_ids) <= MAX_QUESTIONS_PER_CARD:
            raise ValidationError({"question_ids": [f"A card holds 1 to {MAX_QUESTIONS_PER_CARD} questions."]})
        if len(set(payload.question_ids)) != len(payload.question_ids):
            raise ValidationError({"question_ids": ["Duplicate question in the card."]})
        questions = MCQuestion.objects.filter(id__in=payload.question_ids, course=card.course)
        if questions.count() != len(payload.question_ids):
            raise ValidationError({"question_ids": ["A question does not belong to this course."]})
        card.card_questions.all().delete()
        for i, qid in enumerate(payload.question_ids):
            MCCardQuestion.objects.create(card=card, question_id=qid, order=i)
    logger.info("Admin %s updated MC card %d", request.user.username, card_id)
    return _card_payload(card)


@router.delete("/cards/{card_id}", response=None)
def delete_card(request, card_id: int):
    """Delete a card that has no sheets (admin)."""
    _admin_user(request)
    card = MCCard.objects.filter(pk=card_id).first()
    if card is None:
        raise HttpError(404, "Card not found.")
    if card.sheets.exists():
        raise HttpError(409, "Card has sheets and cannot be deleted.")
    card.delete()
    logger.info("Admin %s deleted MC card %d", request.user.username, card_id)


# ---- sheets ---------------------------------------------------------------------
def _sheet_payload(sheet: MCSheet) -> dict:
    """Serialize a sheet for the admin (window + assignment + state)."""
    return {
        "id": sheet.id,
        "card_id": sheet.card_id,
        "card_title": sheet.card.title,
        "course_id": sheet.course_id,
        "window_start": sheet.window_start.isoformat(),
        "window_end": sheet.window_end.isoformat(),
        "number": sheet.number,
        "student_ids": [a.student_id for a in sheet.assignments.order_by("student_id")],
        "question_count": sheet.card.question_count(),
        "submission_count": sheet.submissions.count(),
    }


def _set_students(sheet: MCSheet, course: Course, student_ids: list[int], number: int) -> None:
    """Replace the sheet's student assignments with ``student_ids``."""
    sheet.assignments.all().delete()
    for sid in set(student_ids):
        MCStudentAssignment.objects.create(course=course, student_id=sid, sheet=sheet, number=number)


@router.get("/sheets", response=list[dict])
def list_sheets(request, course_id: int | None = None):
    """List sheets (optionally filtered by course)."""
    _admin_user(request)
    qs = MCSheet.objects.all().select_related("card", "course").prefetch_related("assignments")
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    return [_sheet_payload(s) for s in qs]


@router.post("/sheets", response=dict)
def create_sheet(request, payload: MCSheetIn):
    """Create a time-windowed sheet presenting a card to students (admin)."""
    _admin_user(request)
    course = Course.objects.filter(pk=payload.course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    card = MCCard.objects.filter(pk=payload.card_id, course=course).first()
    if card is None:
        raise HttpError(404, "Card not found in this course.")
    start, end = _parse_dt(payload.window_start), _parse_dt(payload.window_end)
    if end <= start:
        raise ValidationError({"window_end": ["The window must end after it starts."]})
    sheet = MCSheet.objects.create(
        card=card,
        course=course,
        window_start=start,
        window_end=end,
        number=payload.number,
    )
    _set_students(sheet, course, payload.student_ids, payload.number)
    logger.info("Admin %s created MC sheet %d (%s)", request.user.username, sheet.id, card.title)
    return _sheet_payload(sheet)


@router.put("/sheets/{sheet_id}", response=dict)
def update_sheet(request, sheet_id: int, payload: MCSheetIn):
    """
    Update a sheet (admin).

    The window, number and student assignment are always editable. The card can
    only be changed while the sheet has no submissions.
    """
    _admin_user(request)
    sheet = MCSheet.objects.filter(pk=sheet_id).first()
    if sheet is None:
        raise HttpError(404, "Sheet not found.")
    course = Course.objects.filter(pk=payload.course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    start, end = _parse_dt(payload.window_start), _parse_dt(payload.window_end)
    if end <= start:
        raise ValidationError({"window_end": ["The window must end after it starts."]})
    if payload.card_id != sheet.card_id:
        if sheet.submissions.exists():
            raise HttpError(409, "Sheet has submissions; its card can no longer be changed.")
        card = MCCard.objects.filter(pk=payload.card_id, course=course).first()
        if card is None:
            raise HttpError(404, "Card not found in this course.")
        sheet.card = card
    sheet.course = course
    sheet.window_start = start
    sheet.window_end = end
    sheet.number = payload.number
    sheet.save()
    _set_students(sheet, course, payload.student_ids, payload.number)
    logger.info("Admin %s updated MC sheet %d", request.user.username, sheet_id)
    return _sheet_payload(sheet)


@router.delete("/sheets/{sheet_id}", response=None)
def delete_sheet(request, sheet_id: int):
    """Delete a sheet (admin)."""
    _admin_user(request)
    sheet = MCSheet.objects.filter(pk=sheet_id).first()
    if sheet is None:
        raise HttpError(404, "Sheet not found.")
    sheet.delete()
    logger.info("Admin %s deleted MC sheet %d", request.user.username, sheet_id)
