"""Ninja schemas for the analyses API."""

from __future__ import annotations

from typing import Any

from ninja import Schema
from pydantic import BaseModel, Field


class MCResultSummary(BaseModel):
    """Compact multiple-choice result card shown in lists (assistant views)."""

    id: int
    card: str
    number: int
    window_status: str
    submission_count: int
    score: int | None = None
    ideal_score: int | None = None


class AnalysisSummary(BaseModel):
    """Compact analysis card shown in lists (student and assistant views)."""

    id: int
    type: str
    number: int
    label: str = ""
    window_status: str
    submission_count: int
    submission_limit: int
    score: int | None = None
    window_start: str | None = None
    window_end: str | None = None

    @classmethod
    def from_instance(cls, instance: Any) -> AnalysisSummary:
        """Build a summary from an :class:`AnalysisInstance`."""
        return cls(
            id=instance.id,
            type=instance.type.name,
            number=instance.number,
            label=getattr(instance, "label", "") or "",
            window_status=instance.window_status(),
            submission_count=instance.submission_count(),
            submission_limit=instance.submission_limit(),
            score=instance.score(),
            window_start=instance.window_start.isoformat(),
            window_end=instance.window_end.isoformat(),
        )


class AnalysisDetailOut(Schema):
    """Analysis detail: the possible ion set (never the correct one)."""

    id: int
    type: str
    type_description: str
    number: int
    label: str = ""
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
    passing_score: int
    passed: bool
    analyses: list[AnalysisSummary]


# ---- assistant schemas ------------------------------------------------------
class AssistantRosterEntry(Schema):
    """One student row in the course roster view."""

    id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    barcode: str | None
    labspace_id: str | None = None
    analyses: list[AnalysisSummary]
    mc: list[MCResultSummary] = []


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
    # Default submission window inherited by new sessions of this type.
    default_window_start: str | None = None
    default_window_end: str | None = None
    # "New analysis" mode: max re-trial analyses per student/announcement.
    max_repetitions: int | None = None


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


class AnalysisCsvImportOut(Schema):
    """Summary of a CSV import of a course's analyses."""

    course_id: int
    rows: int
    analyses_created: int
    analyses_reused: int
    students_assigned: int
    assignments_skipped: int
    compositions_applied: int = 0


class GradingConfigOut(Schema):
    """Grading configuration (admin read/write)."""

    points_per_correct_ion: int
    penalty_second_submission: int
    penalty_third_submission: int
    false_positive_deduction: int
    grading_mode: str
    max_submissions_per_analysis: int
    final_score_strategy: str
    passing_score: int
    submission_mode: str = "resubmit"
    retry_point_deduction: int = 0
    mc_points_per_card: int = 10
    mc_penalty_per_wrong: int = 2


class AppSettingsOut(Schema):
    """Global app settings (admin read/write)."""

    points_per_analysis: int
    analyses_per_course: int
    active_course_id: int | None
    registration: str = "manual"
    backup_enabled: bool = False
    backup_interval_minutes: int = 60
    backup_location: str = "backups"
    backup_keep: int = 10
    # ---- e-mail notifications (submission confirmations) --------------------
    notify_assistant_on_submission: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_security: str = "tls"
    pgp_public_key: str = ""
    pgp_private_key: str = ""
    pgp_private_key_passphrase: str = ""


class DatabaseBackupOut(Schema):
    """One backup file in the configured location."""

    file: str
    size: int
    modified_at: str
    managed: bool


class DatabaseStatusOut(Schema):
    """Database section status (backend, backup settings, last runs, files)."""

    backend: str
    sqlite: bool
    database_file: str | None
    enabled: bool
    interval_minutes: int
    location: str
    keep: int
    last_backup_at: str | None
    last_backup_file: str | None
    last_restore_at: str | None
    last_restore_file: str | None
    backups: list[DatabaseBackupOut]


class DatabaseRestoreIn(Schema):
    """Payload for restoring the database from a backup file."""

    file: str


class CourseIn(Schema):
    """Course creation/update payload (admin)."""

    name: str
    semester: str = ""
    track: str = ""
    is_active: bool = True
    notify_student_on_submission: bool = False


class StudentOut(Schema):
    """A student, as shown in the admin's student-management views."""

    id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str = ""
    matriculation_no: str = ""
    lab: str = ""
    labspace_id: str = ""
    telephone: str = ""
    course_id: int | None = None
    course_name: str | None = None
    is_active: bool = True


class StudentIn(Schema):
    """Payload for creating a student account (admin)."""

    username: str
    password: str = ""  # empty => a random password is generated and reported
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    matriculation_no: str = ""
    lab: str = ""
    labspace_id: str = ""
    telephone: str = ""
    course_id: int | None = None


class StudentUpdateIn(Schema):
    """
    Payload for updating a student account (admin).

    All fields are optional; only the provided ones are changed. ``password``,
    when non-empty, replaces the student's password. The course assignment is
    managed by the dedicated ``PUT /students/{id}/course`` endpoint.
    """

    username: str | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    matriculation_no: str | None = None
    lab: str | None = None
    labspace_id: str | None = None
    telephone: str | None = None
    is_active: bool | None = None


class StudentCreatedOut(StudentOut):
    """
    :class:`StudentOut` plus the password.

    ``password`` is set when a password was generated for a new account (empty
    ``password`` on create) or when the admin just reset it; ``None`` otherwise.
    """

    password: str | None = None


class StudentImportOut(Schema):
    """Summary of a student CSV import run (admin)."""

    created: int
    updated: int
    skipped: int
    total_rows: int
    errors: list[str]
    generated_passwords: list[dict]


class StudentCourseAssignIn(Schema):
    """Payload for assigning a student to a course (or detaching with ``null``)."""

    student_id: int
    course_id: int | None


class AssistantOut(Schema):
    """An assistant, as shown in the admin's member-management views."""

    id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str = ""
    matriculation_no: str = ""
    lab: str = ""
    labspace_id: str = ""
    telephone: str = ""
    course_id: int | None = None
    course_name: str | None = None
    is_active: bool = True


class AssistantIn(Schema):
    """Payload for creating an assistant account (admin)."""

    username: str
    password: str = ""  # empty => a random password is generated and reported
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    matriculation_no: str = ""
    lab: str = ""
    labspace_id: str = ""
    telephone: str = ""
    course_id: int | None = None


class AssistantUpdateIn(Schema):
    """
    Payload for updating an assistant account (admin).

    All fields are optional; only the provided ones are changed. ``password``,
    when non-empty, replaces the assistant's password. The course assignment is
    managed by the dedicated ``PUT /assistants/{id}/course`` endpoint.
    """

    username: str | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    matriculation_no: str | None = None
    lab: str | None = None
    labspace_id: str | None = None
    telephone: str | None = None
    is_active: bool | None = None


class AssistantCreatedOut(AssistantOut):
    """
    :class:`AssistantOut` plus the password.

    ``password`` is set when a password was generated for a new account (empty
    ``password`` on create) or when the admin just reset it; ``None`` otherwise.
    """

    password: str | None = None


class AssistantCourseAssignIn(Schema):
    """Payload for assigning an assistant to a course (or detaching with ``null``)."""

    assistant_id: int
    course_id: int | None


def _ion_dict(ion: Any) -> dict:
    """Serialize an ion for inclusion in result payloads."""
    return {"id": ion.id, "symbol": ion.symbol, "name": ion.name, "charge": ion.charge, "kind": ion.kind}


def ion_ids_to_dicts(ion_ids: list[int]) -> list[dict]:
    """Resolve a list of ion ids to serialized ion dicts."""
    from substances.models import Ion

    return [_ion_dict(i) for i in Ion.objects.filter(id__in=ion_ids).order_by("id")]
