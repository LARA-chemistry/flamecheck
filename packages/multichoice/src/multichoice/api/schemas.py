"""Ninja schemas for the multiple-choice API."""

from __future__ import annotations

from ninja import Schema


class MCOptionIn(Schema):
    """One answer option when creating/updating a question."""

    text: str
    is_correct: bool = False
    sort_order: int = 0


class MCQuestionIn(Schema):
    """Payload for creating/updating a multiple-choice question."""

    text: str
    description: str | None = ""
    remarks: str | None = ""
    # Optional on update (None = leave options unchanged); required on create.
    options: list[MCOptionIn] | None = None


class MCQuestionOut(Schema):
    """A question with its options (admin view; includes the correct flag)."""

    id: int
    text: str
    description: str
    remarks: str
    options: list[MCOptionIn]
    card_count: int = 0


class MCCardIn(Schema):
    """Payload for creating/updating a card (1..3 questions, in order)."""

    title: str
    description: str | None = ""
    remarks: str | None = ""
    question_ids: list[int]


class MCCardOut(Schema):
    """A card with its ordered questions (admin view)."""

    id: int
    title: str
    description: str
    remarks: str
    questions: list[dict]
    sheet_count: int = 0


class MCSheetIn(Schema):
    """Payload for creating/updating a time-windowed sheet."""

    card_id: int
    course_id: int | None = None
    window_start: str
    window_end: str
    number: int = 1
    student_ids: list[int] = []


class MCSheetOut(Schema):
    """A sheet with window, assignment and submission state (admin view)."""

    id: int
    card_id: int
    card_title: str
    course_id: int | None
    window_start: str
    window_end: str
    number: int
    student_ids: list[int]
    question_count: int
    submission_count: int


class MCSubmissionIn(Schema):
    """Payload for a student's submission: question id -> selected option id."""

    answers: dict[str, int]
    idempotency_key: str


class MCSheetSummary(Schema):
    """A compact card for the student's home grid."""

    id: int
    card_title: str
    number: int
    window_status: str
    window_start: str
    window_end: str
    submission_count: int
    score: int | None = None
    question_count: int
