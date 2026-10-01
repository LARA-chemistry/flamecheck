"""Ninja schemas for the analyses API."""

from __future__ import annotations

from typing import Any

from ninja import Schema
from pydantic import BaseModel, Field


class AnalysisSummary(BaseModel):
    """Compact analysis card shown in lists (student and assistant views)."""

    id: int
    type: str
    number: int
    window_status: str
    submission_count: int
    submission_limit: int
    score: int | None = None

    @classmethod
    def from_instance(cls, instance: Any) -> AnalysisSummary:
        """Build a summary from an :class:`AnalysisInstance`."""
        return cls(
            id=instance.id,
            type=instance.type.name,
            number=instance.number,
            window_status=instance.window_status(),
            submission_count=instance.submission_count(),
            submission_limit=instance.submission_limit(),
            score=instance.score(),
        )


class AnalysisDetailOut(Schema):
    """Analysis detail: the possible ion set (never the correct one)."""

    id: int
    type: str
    type_description: str
    number: int
    window_status: str
    window_start: str
    window_end: str
    submission_count: int
    submission_limit: int
    cations: list[dict]
    anions: list[dict]


class SubmissionIn(BaseModel):
    """Payload for creating a submission."""

    ion_ids: list[int] = Field(default_factory=list, description="IDs of the selected ions.")
    confirmed: bool = Field(description="Client confirmation that the selection is final.")
    idempotency_key: str = Field(description="Client-generated key (UUID) preventing duplicate submissions.")


class SubmissionOut(Schema):
    """A single submission in the student's history."""

    id: int
    submission_number: int
    score: int
    correct_count: int
    wrong_count: int
    missing_count: int
    penalty: int
    ideal_score: int
    submitted_at: str


class ResultOut(Schema):
    """The 'Kontrollabfrage' result revealed after submission."""

    analysis_id: int
    submissions: list[SubmissionResultOut]
    total_score: int
    ideal_score: int


class SubmissionResultOut(Schema):
    """Result of one submission: ion breakdown + scores."""

    id: int
    submission_number: int
    submitted_at: str
    score: int
    penalty: int
    ideal_score: int
    correct_ions: list[dict]
    wrong_ions: list[dict]
    missing_ions: list[dict]


class SummaryOut(Schema):
    """The student's overall summary across all assigned analyses."""

    total_score: int
    ideal_score: int
    analyses: list[AnalysisSummary]


# ---- assistant schemas ------------------------------------------------------
class AssistantRosterEntry(Schema):
    """One student row in the course roster view."""

    id: int
    username: str
    name: str | None
    barcode: str | None
    analyses: list[AnalysisSummary]


class AssistantCourseOut(Schema):
    """Assistant view of one course: students + submissions."""

    id: int
    name: str
    semester: str
    is_active: bool
    students: list[AssistantRosterEntry]
    stats: dict


class StudentSubmissionsOut(Schema):
    """Assistant detail view of one student's submissions for an analysis."""

    student: str
    analysis: str
    submissions: list[dict]
    correct_ions: list[dict]


# ---- admin schemas ----------------------------------------------------------
class AnalysisTypeIn(Schema):
    """Payload for creating/updating an analysis type."""

    name: str
    description: str | None = None
    ion_ids: list[int] | None = None


class AnalysisInstanceIn(Schema):
    """Payload for creating/updating an analysis instance (admin)."""

    type_id: int | None = None
    course_id: int | None = None
    number: int | None = None
    window_start: str | None = None
    window_end: str | None = None
    correct_ion_ids: list[int] | None = None


class AssignmentIn(Schema):
    """Payload for assigning an analysis instance to a student."""

    instance_id: int
    student_id: int
    number: int | None = None


class RandomizeSubstancesIn(Schema):
    """Payload for randomly assigning substances to a course's announcement."""

    course_id: int
    number: int
    min_ions: int = 3
    max_ions: int = 5


class RandomizeSubstancesStudentOut(Schema):
    """Per-student outcome of a randomize run."""

    student_id: int
    student: str
    instance_id: int
    correct_ions: list[dict]
    substances: list[dict]


class RandomizeSubstancesOut(Schema):
    """Summary of a random substance-assignment run."""

    course_id: int
    number: int
    randomized: int
    students: list[RandomizeSubstancesStudentOut]


class GradingConfigOut(Schema):
    """Grading configuration (admin read/write)."""

    points_per_correct_ion: int
    penalty_second_submission: int
    penalty_third_submission: int
    false_positive_deduction: int
    grading_mode: str
    max_submissions_per_analysis: int
    final_score_strategy: str


class AppSettingsOut(Schema):
    """Global app settings (admin read/write)."""

    points_per_analysis: int
    analyses_per_course: int
    active_course_id: int | None


class CourseIn(Schema):
    """Course creation/update payload (admin)."""

    name: str
    semester: str = ""
    track: str = ""
    is_active: bool = True


class StudentOut(Schema):
    """A student, as shown in the admin's student-management views."""

    id: int
    username: str
    name: str | None = None
    course_id: int | None = None
    course_name: str | None = None
    is_active: bool = True


class StudentCourseAssignIn(Schema):
    """Payload for assigning a student to a course (or detaching with ``null``)."""

    student_id: int
    course_id: int | None


def _ion_dict(ion: Any) -> dict:
    """Serialize an ion for inclusion in result payloads."""
    return {"id": ion.id, "symbol": ion.symbol, "name": ion.name, "charge": ion.charge, "kind": ion.kind}


def ion_ids_to_dicts(ion_ids: list[int]) -> list[dict]:
    """Resolve a list of ion ids to serialized ion dicts."""
    from substances.models import Ion

    return [_ion_dict(i) for i in Ion.objects.filter(id__in=ion_ids).order_by("id")]
