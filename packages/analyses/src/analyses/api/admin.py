"""
Admin endpoints: CRUD for analysis types, instances, assignments, grading config.

All mutating endpoints are admin-only and logged to the audit logger.
"""

from __future__ import annotations

import csv
import io
import logging
import secrets
from datetime import UTC, datetime

from analyses.api.schemas import (
    AnalysisCsvImportOut,
    AnalysisInstanceIn,
    AnalysisTypeIn,
    AppSettingsOut,
    AssignmentIn,
    AssistantCourseAssignIn,
    AssistantCreatedOut,
    AssistantIn,
    AssistantOut,
    AssistantUpdateIn,
    CourseIn,
    DatabaseRestoreIn,
    DatabaseStatusOut,
    GradingConfigOut,
    RandomizeSubstancesIn,
    RandomizeSubstancesOut,
    RandomizeSubstancesStudentOut,
    StudentCourseAssignIn,
    StudentCreatedOut,
    StudentImportOut,
    StudentIn,
    StudentOut,
    StudentUpdateIn,
)
from analyses.models import AnalysisInstance, AnalysisType
from analyses.services import InsufficientIonsError, randomize_substances_for_announcement
from analyses.services.csv_import import (
    MAX_UPLOAD_BYTES,
    CsvImportError,
    import_analyses_csv,
    render_template,
)
from config import db_backup
from config.models import AppSettings, Course, GradingConfig
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from ninja import File, Form, Router
from ninja.errors import AuthenticationError, HttpError, ValidationError
from ninja.files import UploadedFile
from substances.api.schemas import ion_to_schema, substance_to_schema
from substances.models import Ion, Substance
from users.models import StudentAssignment, User

logger = logging.getLogger("flamecheck.audit")

router = Router(tags=["admin"])


def _admin_user(request) -> User:
    """Return the request user if admin, else raise 401."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    if not user.is_admin:
        raise AuthenticationError(403, "Admin role required.")
    return user


def _parse_dt(value: str) -> datetime:
    """Parse an ISO-8601 datetime (with or without trailing Z)."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


# ---- courses -----------------------------------------------------------------
@router.get("/courses", response=list[dict])
def list_courses(request):
    """List all courses (admin)."""
    _admin_user(request)
    return [
        {"id": c.id, "name": c.name, "semester": c.semester, "track": c.track, "is_active": c.is_active}
        for c in Course.objects.all()
    ]


@router.post("/courses", response=dict)
def create_course(request, payload: CourseIn):
    """Create a course (admin)."""
    _admin_user(request)
    course = Course.objects.create(
        name=payload.name,
        semester=payload.semester,
        track=payload.track,
        is_active=payload.is_active,
    )
    logger.info("Admin %s created course %s", request.user.username, course.name)
    return {"id": course.id, "name": course.name}


@router.put("/courses/{course_id}", response=dict)
def update_course(request, course_id: int, payload: CourseIn):
    """Update a course (admin)."""
    _admin_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    course.name = payload.name
    course.semester = payload.semester
    course.track = payload.track
    course.is_active = payload.is_active
    course.save()
    logger.info("Admin %s updated course %s", request.user.username, course.name)
    return {"id": course.id, "name": course.name}


@router.delete("/courses/{course_id}", response=None)
def delete_course(request, course_id: int):
    """Delete a course (admin). Refused while students or analyses still reference it."""
    _admin_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    if course.students.exists() or course.analysis_instances.exists() or course.assignments.exists():
        raise HttpError(409, "Course still has students, analyses or assignments and cannot be deleted.")
    course.delete()
    logger.info("Admin %s deleted course %s", request.user.username, course_id)


# ---- students ------------------------------------------------------------------
# Header row for the student CSV import format (also used for the downloadable
# template). Columns are separated by ``;`` (a comma is accepted as well).
STUDENT_CSV_HEADER = [
    "username",
    "name",
    "email",
    "matriculation_no",
    "lab",
    "labspace_id",
    "telephone",
    "course",
    "password",
]


def _student_to_out(s: User) -> dict:
    """Serialize a student :class:`~users.models.User` into the API payload."""
    return {
        "id": s.id,
        "username": s.username,
        "name": s.name or None,
        "email": s.email or "",
        "matriculation_no": s.matriculation_no or "",
        "lab": s.lab or "",
        "labspace_id": s.labspace_id or "",
        "telephone": s.telephone or "",
        "course_id": s.course_id,
        "course_name": s.course.name if s.course else None,
        "is_active": s.is_active,
    }


def _generate_student_password() -> str:
    """
    Generate a random initial password for a new student account.

    Guaranteed to mix upper/lower case and a digit so it passes the configured
    password validators; re-validated with ``validate_password`` just in case.
    """
    lower = "abcdefghijkmnopqrstuvwxyz"
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    while True:
        chars = [secrets.choice(lower), secrets.choice(upper), secrets.choice(digits)]
        chars += [secrets.choice(lower + upper + digits) for _ in range(9)]
        secrets.SystemRandom().shuffle(chars)
        candidate = "".join(chars)
        try:
            validate_password(candidate)
            return candidate
        except DjangoValidationError:  # pragma: no cover - effectively impossible
            continue


def _validate_or_raise(password: str) -> None:
    """Raise an API validation error when ``password`` fails the validators."""
    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from exc


def _set_student_fields(student: User, row: dict) -> None:
    """Copy the editable info columns from a CSV row onto ``student``."""
    student.name = (row.get("name") or "").strip()
    student.email = (row.get("email") or "").strip()
    student.matriculation_no = (row.get("matriculation_no") or "").strip()
    student.lab = (row.get("lab") or "").strip()
    student.labspace_id = (row.get("labspace_id") or "").strip()
    student.telephone = (row.get("telephone") or "").strip()


def _list_members(request, role: User.Role, course_id: int | None) -> list[dict]:
    """List users with ``role`` (admin), optionally filtered by their course."""
    _admin_user(request)
    qs = User.objects.filter(role=role).select_related("course")
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    return [_student_to_out(u) for u in qs]


@router.get("/students", response=list[StudentOut])
def list_students(request, course_id: int | None = None):
    """List students (admin), optionally filtered by their course."""
    return _list_members(request, User.Role.STUDENT, course_id)


@router.get("/assistants", response=list[AssistantOut])
def list_assistants(request, course_id: int | None = None):
    """List assistants (admin), optionally filtered by their course."""
    return _list_members(request, User.Role.ASSISTANT, course_id)


# NOTE: the literal ``/students/import-*`` routes must be registered before the
# ``/students/{student_id}`` routes below.
@router.get("/students/import-template", response=None, operation_id="student_import_template")
def student_import_template(request):
    """Return a sample CSV showing the expected student import format (admin)."""
    _admin_user(request)
    sample = "\n".join(
        [
            ";".join(STUDENT_CSV_HEADER),
            # username;name;email;matriculation_no;lab;labspace_id;telephone;course;password
            "jdoe;Jane Doe;jane.doe@example.com;M123456;Inorganic, Biology track;LS-000123;"
            "+49 151 2345678;Inorganic Chemistry WS 2026;Welcome123!",
            "asmith;Ann Smith;;M765432;;;;Inorganic Chemistry WS 2026;",
        ]
    )
    response = HttpResponse(sample, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="students_import_template.csv"'
    return response


@router.post("/students/import-csv", response=StudentImportOut)
def import_students_csv(request, file: UploadedFile = File(...)):  # noqa: B008
    """
    Bulk-create/update students from an uploaded CSV file (admin).

    Columns (first row is a header): ``username`` (required, unique key),
    ``name``, ``email``, ``matriculation_no``, ``lab``, ``labspace_id``,
    ``telephone``, ``course`` (course *name*, empty for no course), ``password``
    (only used for new students; leave empty to auto-generate one, which is
    then reported in ``generated_passwords``). Columns are separated by ``;``
    (a comma is accepted as well). Rows are matched by username: a match
    updates the existing student (the ``password`` column is ignored for
    updates, and an empty ``course`` keeps the current course), otherwise a
    new student account is created.
    """
    _admin_user(request)
    raw = file.read()
    if not raw:
        raise ValidationError({"file": ["The uploaded file is empty."]})
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": [f"File too large (max {MAX_UPLOAD_BYTES // 1024} KB)."]})
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError({"file": [f"File is not valid UTF-8: {exc}"]}) from exc

    delim = ";" if ";" in text.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    fieldnames = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
    if "username" not in fieldnames:
        raise ValidationError({"file": ["CSV must have a header row with a 'username' column."]})

    courses = {c.name.lower(): c for c in Course.objects.all()}
    created = updated = skipped = 0
    errors: list[str] = []
    generated_passwords: list[dict] = []

    for line_no, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): v for k, v in row.items()}
        username = (row.get("username") or "").strip()
        if not username:
            skipped += 1
            errors.append(f"Line {line_no}: missing 'username' - skipped.")
            continue
        course_name = (row.get("course") or "").strip()
        course = courses.get(course_name.lower()) if course_name else None
        if course_name and course is None:
            skipped += 1
            errors.append(f"Line {line_no} ({username}): unknown course '{course_name}' - skipped.")
            continue
        existing = User.objects.filter(username__iexact=username, role=User.Role.STUDENT).first()
        if existing is not None:
            _set_student_fields(existing, row)
            if course is not None:
                existing.course = course
            existing.save()
            updated += 1
            continue
        if User.objects.filter(username__iexact=username).exists():
            skipped += 1
            errors.append(f"Line {line_no}: username '{username}' is already taken by a non-student - skipped.")
            continue
        password = (row.get("password") or "").strip()
        if password:
            try:
                validate_password(password)
            except DjangoValidationError as exc:
                skipped += 1
                errors.append(f"Line {line_no} ({username}): invalid password ({'; '.join(exc.messages)}) - skipped.")
                continue
        else:
            password = _generate_student_password()
            generated_passwords.append({"username": username, "password": password})
        student = User(username=username, role=User.Role.STUDENT, is_active=True)
        student.set_password(password)
        _set_student_fields(student, row)
        student.course = course
        student.save()
        created += 1

    logger.info(
        "Admin %s imported students CSV: %d created, %d updated, %d skipped",
        request.user.username,
        created,
        updated,
        skipped,
    )
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_rows": created + updated + skipped,
        "errors": errors[:50],
        "generated_passwords": generated_passwords,
    }


def _member_label(role: User.Role) -> str:
    """Human label for a member role used in log messages and error texts."""
    return "assistant" if role == User.Role.ASSISTANT else "student"


def _create_member(request, role: User.Role, payload) -> dict:
    """Create a member account (student or assistant); empty password auto-generates."""
    _admin_user(request)
    if User.objects.filter(username__iexact=payload.username).exists():
        raise HttpError(409, f"Username '{payload.username}' is already taken.")
    if payload.course_id is not None and not Course.objects.filter(pk=payload.course_id).exists():
        raise HttpError(404, "Course not found.")
    password = payload.password
    generated = False
    if password:
        _validate_or_raise(password)
    else:
        password = _generate_student_password()
        generated = True
    member = User(username=payload.username, role=role, is_active=True)
    member.set_password(password)
    member.name = payload.name
    member.email = payload.email
    member.matriculation_no = payload.matriculation_no
    member.lab = payload.lab
    member.labspace_id = payload.labspace_id
    member.telephone = payload.telephone
    member.course_id = payload.course_id
    member.save()
    logger.info(
        "Admin %s created %s %s (auto password: %s)",
        request.user.username,
        _member_label(role),
        payload.username,
        generated,
    )
    out = _student_to_out(member)
    if generated:
        out["password"] = password
    return out


def _update_member(request, role: User.Role, member_id: int, payload) -> dict:
    """Update a member account (student or assistant); only provided fields change."""
    _admin_user(request)
    member = User.objects.filter(pk=member_id, role=role).first()
    if member is None:
        raise HttpError(404, f"{_member_label(role).capitalize()} not found.")
    if payload.username is not None and payload.username != member.username:
        if User.objects.filter(username__iexact=payload.username).exclude(pk=member.pk).exists():
            raise HttpError(409, f"Username '{payload.username}' is already taken.")
        member.username = payload.username
    if payload.password:
        _validate_or_raise(payload.password)
        member.set_password(payload.password)
    if payload.name is not None:
        member.name = payload.name
    if payload.email is not None:
        member.email = payload.email
    if payload.matriculation_no is not None:
        member.matriculation_no = payload.matriculation_no
    if payload.lab is not None:
        member.lab = payload.lab
    if payload.labspace_id is not None:
        member.labspace_id = payload.labspace_id
    if payload.telephone is not None:
        member.telephone = payload.telephone
    if payload.is_active is not None:
        member.is_active = payload.is_active
    member.save()
    logger.info("Admin %s updated %s %s", request.user.username, _member_label(role), member.username)
    out = _student_to_out(member)
    if payload.password:
        out["password"] = payload.password
    return out


def _delete_member(request, role: User.Role, member_id: int) -> dict:
    """
    Delete a member account (student or assistant) (admin).

    Refused with 409 while the member still has submissions (their results must
    be preserved); course assignments and barcodes are removed.
    """
    _admin_user(request)
    member = User.objects.filter(pk=member_id, role=role).first()
    if member is None:
        raise HttpError(404, f"{_member_label(role).capitalize()} not found.")
    if member.submissions.exists():
        raise HttpError(409, f"{_member_label(role).capitalize()} has submissions and cannot be deleted.")
    username = member.username
    member.delete()
    logger.info("Admin %s deleted %s %s", request.user.username, _member_label(role), username)
    return {"id": member_id, "deleted": True}


def _assign_member_course(request, role: User.Role, member_id: int, course_id: int | None) -> dict:
    """Set (or clear, with ``course_id = null``) a member's course (admin)."""
    _admin_user(request)
    member = User.objects.filter(pk=member_id, role=role).first()
    if member is None:
        raise HttpError(404, f"{_member_label(role).capitalize()} not found.")
    if course_id is not None:
        course = Course.objects.filter(pk=course_id).first()
        if course is None:
            raise HttpError(404, "Course not found.")
        member.course = course
    else:
        member.course = None
    member.save(update_fields=["course"])
    logger.info(
        "Admin %s set course for %s %s to %s",
        request.user.username,
        _member_label(role),
        member.username,
        course_id,
    )
    return {"id": member.id, "username": member.username, "course_id": member.course_id}


@router.post("/students", response=StudentCreatedOut)
def create_student(request, payload: StudentIn):
    """Create a student account (admin). An empty ``password`` is auto-generated."""
    return _create_member(request, User.Role.STUDENT, payload)


@router.put("/students/{student_id}", response=StudentCreatedOut)
def update_student(request, student_id: int, payload: StudentUpdateIn):
    """Update a student account (admin); only provided fields are changed."""
    return _update_member(request, User.Role.STUDENT, student_id, payload)


@router.delete("/students/{student_id}", response=dict)
def delete_student(request, student_id: int):
    """Delete a student account (admin); refused while they have submissions."""
    return _delete_member(request, User.Role.STUDENT, student_id)


@router.put("/students/{student_id}/course", response=dict)
def assign_student_course(request, student_id: int, payload: StudentCourseAssignIn):
    """Assign a student to a course (or detach with ``course_id = null``) (admin)."""
    return _assign_member_course(request, User.Role.STUDENT, payload.student_id, payload.course_id)


@router.post("/assistants", response=AssistantCreatedOut)
def create_assistant(request, payload: AssistantIn):
    """Create an assistant account (admin). An empty ``password`` is auto-generated."""
    return _create_member(request, User.Role.ASSISTANT, payload)


@router.put("/assistants/{assistant_id}", response=AssistantCreatedOut)
def update_assistant(request, assistant_id: int, payload: AssistantUpdateIn):
    """Update an assistant account (admin); only provided fields are changed."""
    return _update_member(request, User.Role.ASSISTANT, assistant_id, payload)


@router.delete("/assistants/{assistant_id}", response=dict)
def delete_assistant(request, assistant_id: int):
    """Delete an assistant account (admin); refused while they have submissions."""
    return _delete_member(request, User.Role.ASSISTANT, assistant_id)


@router.put("/assistants/{assistant_id}/course", response=dict)
def assign_assistant_course(request, assistant_id: int, payload: AssistantCourseAssignIn):
    """Assign an assistant to a course (or detach with ``course_id = null``) (admin)."""
    return _assign_member_course(request, User.Role.ASSISTANT, payload.assistant_id, payload.course_id)


# ---- analysis types ------------------------------------------------------------
@router.get("/analysis-types", response=list[dict])
def list_analysis_types(request):
    """List all analysis types with their possible ion sets."""
    _admin_user(request)
    types = AnalysisType.objects.all().prefetch_related("possible_ions")
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "ions": [ion_to_schema(i) for i in t.possible_ions.all()],
            "default_window_start": t.default_window_start.isoformat() if t.default_window_start else None,
            "default_window_end": t.default_window_end.isoformat() if t.default_window_end else None,
            "session_count": t.instances.count(),
        }
        for t in types
    ]


@router.post("/analysis-types", response=dict)
def create_analysis_type(request, payload: AnalysisTypeIn):
    """Create an analysis type (admin)."""
    _admin_user(request)
    t = AnalysisType.objects.create(name=payload.name, description=payload.description or "")
    if payload.ion_ids:
        t.possible_ions.set(payload.ion_ids)
    if payload.default_window_start:
        t.default_window_start = _parse_dt(payload.default_window_start)
    if payload.default_window_end:
        t.default_window_end = _parse_dt(payload.default_window_end)
    t.save()
    logger.info("Admin %s created analysis type %s", request.user.username, t.name)
    return {"id": t.id, "name": t.name}


@router.put("/analysis-types/{type_id}", response=dict)
def update_analysis_type(request, type_id: int, payload: AnalysisTypeIn):
    """Update an analysis type (admin)."""
    _admin_user(request)
    t = AnalysisType.objects.get(pk=type_id)
    t.name = payload.name
    t.description = payload.description if payload.description is not None else t.description
    # Default window: a provided value replaces it, an empty value clears it.
    if payload.default_window_start:
        t.default_window_start = _parse_dt(payload.default_window_start)
    elif payload.default_window_start is None:
        t.default_window_start = None
    if payload.default_window_end:
        t.default_window_end = _parse_dt(payload.default_window_end)
    elif payload.default_window_end is None:
        t.default_window_end = None
    t.save()
    if payload.ion_ids is not None:
        t.possible_ions.set(payload.ion_ids)
    logger.info("Admin %s updated analysis type %s", request.user.username, t.name)
    return {"id": t.id, "name": t.name}


@router.delete("/analysis-types/{type_id}", response=None)
def delete_analysis_type(request, type_id: int):
    """Delete an analysis type that has no instances (admin)."""
    _admin_user(request)
    t = AnalysisType.objects.get(pk=type_id)
    if t.instances.exists():
        raise HttpError(409, "Type has instances and cannot be deleted.")
    t.delete()
    logger.info("Admin %s deleted analysis type %s", request.user.username, type_id)


# ---- analysis instances ---------------------------------------------------------
@router.get("/analysis-instances", response=list[dict])
def list_analysis_instances(request, course_id: int | None = None, type_id: int | None = None):
    """List analysis instances (admin), optionally filtered by course and/or type."""
    _admin_user(request)
    qs = AnalysisInstance.objects.all().prefetch_related("correct_ions", "type", "assignments__student")
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    if type_id is not None:
        qs = qs.filter(type_id=type_id)
    return [
        {
            "id": i.id,
            "type_id": i.type_id,
            "type": i.type.name,
            "number": i.number,
            "course": i.course.name if i.course else None,
            "course_id": i.course_id,
            "window_start": i.window_start.isoformat(),
            "window_end": i.window_end.isoformat(),
            "correct_ions": [ion_to_schema(x) for x in i.correct_ions.all()],
            "assigned_students": [a.student.username for a in i.assignments.all()],
        }
        for i in qs
    ]


@router.post("/analysis-instances", response=dict)
def create_analysis_instance(request, payload: AnalysisInstanceIn):
    """
    Create an analysis instance (admin).

    The window may be omitted; in that case the analysis type's default window
    is inherited so a session created from a freshly defined type has a usable
    window out of the box.
    """
    _admin_user(request)
    t = AnalysisType.objects.get(pk=payload.type_id)
    # Resolve the window: explicit values win, otherwise fall back to the
    # type's default window. At least one bound must end up set.
    if payload.window_start:
        start = _parse_dt(payload.window_start)
    elif t.default_window_start:
        start = t.default_window_start
    else:
        raise HttpError(400, "window_start is required (set it or a type default).")
    if payload.window_end:
        end = _parse_dt(payload.window_end)
    elif t.default_window_end:
        end = t.default_window_end
    else:
        raise HttpError(400, "window_end is required (set it or a type default).")
    if end <= start:
        raise HttpError(400, "window_end must be after window_start.")
    course = Course.objects.filter(pk=payload.course_id).first() if payload.course_id else None
    inst = AnalysisInstance.objects.create(
        type=t,
        course=course,
        number=payload.number,
        window_start=start,
        window_end=end,
    )
    if payload.correct_ion_ids:
        inst.correct_ions.set(payload.correct_ion_ids)
    logger.info("Admin %s created analysis instance %s", request.user.username, inst)
    return {"id": inst.id, "type": t.name}


# NOTE: this literal route must be registered before the
# ``/analysis-instances/{instance_id}`` routes, or the parameterized routes shadow it.
@router.post("/analysis-instances/randomize-substances", response=RandomizeSubstancesOut)
def randomize_substances(request, payload: RandomizeSubstancesIn):
    """
    Randomly assign substances to the students of a course's announcement (admin).

    For every student assigned to the given ``course_id`` + ``number``, a random
    subset of the analysis type's possible ions (size in ``[min_ions, max_ions]``)
    becomes that student's answer key, and the matching substances are recorded as
    their assigned substances. Returns the per-student outcome.
    """
    _admin_user(request)
    course = Course.objects.filter(pk=payload.course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    if not AnalysisInstance.objects.filter(course=course, number=payload.number).exists():
        raise HttpError(404, f"No analysis instances for course {payload.course_id} number {payload.number}.")
    try:
        results = randomize_substances_for_announcement(
            course,
            payload.number,
            min_ions=payload.min_ions,
            max_ions=payload.max_ions,
        )
    except InsufficientIonsError as exc:
        raise HttpError(400, str(exc)) from exc

    # Resolve ion/substance ids to display dicts once (shared across students).
    all_ion_ids = {ion_id for r in results for ion_id in r.correct_ion_ids}
    all_sub_ids = {s_id for r in results for s_id in r.assigned_substance_ids}
    ion_map = (
        {i.id: ion_to_schema(i) for i in Ion.objects.filter(id__in=all_ion_ids).order_by("kind", "symbol")}
        if all_ion_ids
        else {}
    )
    sub_map = (
        {
            s.id: substance_to_schema(s)
            for s in Substance.objects.filter(id__in=all_sub_ids).prefetch_related("ions").order_by("name")
        }
        if all_sub_ids
        else {}
    )

    students_out = [
        RandomizeSubstancesStudentOut(
            student_id=r.student_id,
            student=r.student_name,
            instance_id=r.instance_id,
            correct_ions=[ion_map[i] for i in r.correct_ion_ids if i in ion_map],
            substances=[sub_map[s] for s in r.assigned_substance_ids if s in sub_map],
        )
        for r in results
    ]
    logger.info(
        "Admin %s randomized substances for course %s number %s (%d students)",
        request.user.username,
        course.name,
        payload.number,
        len(results),
    )
    return {
        "course_id": course.id,
        "number": payload.number,
        "randomized": len(results),
        "students": students_out,
    }


# NOTE: these literal routes must stay ahead of the parameterized
# ``/analysis-instances/{instance_id}`` routes below.
@router.get("/analysis-instances/template-csv", response=None)
def download_analyses_template(request, course_id: int):
    """
    Download a CSV template for importing a set of analyses for a course.

    The template has one example row per analysis type; window columns are
    empty (rows then inherit the type's default window) and the labspace_id /
    substances columns are left empty for the admin to fill in. Columns are
    ``;``-separated and the composition (substances) cell is ``,``-separated.
    """
    _admin_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    response = HttpResponse(render_template(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="analysis_import_template_course_{course.id}.csv"'
    return response


@router.post("/analysis-instances/import-csv", response=AnalysisCsvImportOut)
def upload_analyses_csv(
    request,
    course_id: int = Form(...),
    file: UploadedFile = File(...),  # noqa: B008
):
    """
    Upload a CSV with a set of analyses for a course (admin).

    Each row is one student's analysis: it references an analysis type by
    name, an announcement number, an optional window (falling back to the
    type's default), the student's Labspace ID, and the composition — the
    salts/compounds present, comma-separated. The composition becomes the
    student's answer key (the union of the ions the substances provide) and
    the reference substances. Columns are ``;``-separated; the composition
    cell is ``,``-separated. Existing (student, course, number) instances are
    reused and existing assignments skipped, so re-uploads are safe. Invalid
    files are rejected atomically with all issues reported.
    """
    _admin_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    data = file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HttpError(400, f"File too large (max {MAX_UPLOAD_BYTES // 1024} KB).")
    try:
        summary = import_analyses_csv(course, data)
    except CsvImportError as exc:
        raise HttpError(400, "; ".join(exc.issues)) from exc
    logger.info(
        "Admin %s imported %d analysis rows for course %s (%d created, %d reused, %d assigned, %d compositions)",
        request.user.username,
        summary.rows,
        course.name,
        summary.analyses_created,
        summary.analyses_reused,
        summary.students_assigned,
        summary.compositions_applied,
    )
    return {
        "course_id": summary.course_id,
        "rows": summary.rows,
        "analyses_created": summary.analyses_created,
        "analyses_reused": summary.analyses_reused,
        "students_assigned": summary.students_assigned,
        "assignments_skipped": summary.assignments_skipped,
        "compositions_applied": summary.compositions_applied,
    }


@router.put("/analysis-instances/{instance_id}", response=dict)
def update_analysis_instance(request, instance_id: int, payload: AnalysisInstanceIn):
    """Update an analysis instance's window/correct set/number (admin)."""
    _admin_user(request)
    inst = AnalysisInstance.objects.get(pk=instance_id)
    if payload.window_start:
        inst.window_start = _parse_dt(payload.window_start)
    if payload.window_end:
        inst.window_end = _parse_dt(payload.window_end)
    if payload.number is not None:
        inst.number = payload.number
    if payload.correct_ion_ids:
        inst.correct_ions.set(payload.correct_ion_ids)
    if payload.course_id is not None:
        inst.course_id = payload.course_id
    inst.save()
    logger.info("Admin %s updated analysis instance %s", request.user.username, instance_id)
    return {"id": inst.id}


@router.delete("/analysis-instances/{instance_id}", response=None)
def delete_analysis_instance(request, instance_id: int):
    """Delete an analysis instance (admin). Only allowed if no submissions exist."""
    _admin_user(request)
    inst = AnalysisInstance.objects.get(pk=instance_id)
    if inst.submissions.exists():
        raise HttpError(409, "Instance has submissions and cannot be deleted.")
    inst.delete()
    logger.info("Admin %s deleted analysis instance %s", request.user.username, instance_id)


# ---- assignments -----------------------------------------------------------------
@router.get("/assignments", response=list[dict])
def list_assignments(request, course_id: int | None = None):
    """List student - instance assignments (admin)."""
    _admin_user(request)
    qs = StudentAssignment.objects.all().select_related("student", "instance", "instance__type", "course")
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    return [
        {
            "id": a.id,
            "course": a.course.name if a.course else None,
            "student": a.student.username,
            "student_id": a.student_id,
            "instance_id": a.instance_id,
            "analysis": a.instance.type.name,
            "number": a.number,
        }
        for a in qs
    ]


@router.post("/assignments", response=dict)
def create_assignment(request, payload: AssignmentIn):
    """Assign an analysis instance to a student (admin)."""
    _admin_user(request)
    instance = AnalysisInstance.objects.get(pk=payload.instance_id)
    student = User.objects.filter(pk=payload.student_id).first()
    if student is None:
        raise HttpError(404, "Student not found.")
    course = instance.course
    assignment = StudentAssignment.objects.create(
        course=course,
        student=student,
        instance=instance,
        number=payload.number or instance.number,
    )
    logger.info("Admin %s assigned %s to %s", request.user.username, student.username, instance)
    return {"id": assignment.id, "student": student.username, "instance_id": instance.id}


@router.delete("/assignments/{assignment_id}", response=None)
def delete_assignment(request, assignment_id: int):
    """Remove an assignment (admin)."""
    _admin_user(request)
    assignment = StudentAssignment.objects.get(pk=assignment_id)
    logger.info("Admin %s removed assignment %s", request.user.username, assignment_id)
    assignment.delete()


# ---- grading config --------------------------------------------------------------
@router.get("/grading-config", response=GradingConfigOut)
def get_grading_config(request):
    """Read the grading configuration (any authenticated user; writes are admin-only)."""
    if not getattr(request.user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    gc = GradingConfig.get_instance()
    return _grading_config_payload(gc)


@router.put("/grading-config", response=GradingConfigOut)
def update_grading_config(request, payload: GradingConfigOut):
    """Update the global (default) grading configuration (admin)."""
    _admin_user(request)
    gc = GradingConfig.get_instance()
    _apply_grading_payload(gc, payload)
    gc.save()
    logger.info("Admin %s updated global grading config", request.user.username)
    return _grading_config_payload(gc)


def _apply_grading_payload(gc: GradingConfig, payload: GradingConfigOut) -> None:
    """Copy the grading fields from ``payload`` onto ``gc`` (no save)."""
    gc.points_per_correct_ion = payload.points_per_correct_ion
    gc.penalty_second_submission = payload.penalty_second_submission
    gc.penalty_third_submission = payload.penalty_third_submission
    gc.false_positive_deduction = payload.false_positive_deduction
    gc.grading_mode = payload.grading_mode
    gc.max_submissions_per_analysis = payload.max_submissions_per_analysis
    gc.final_score_strategy = payload.final_score_strategy
    gc.passing_score = payload.passing_score


def _grading_config_payload(gc: GradingConfig) -> dict:
    """Serialize a :class:`GradingConfig` into the :class:`GradingConfigOut` shape."""
    return {
        "points_per_correct_ion": gc.points_per_correct_ion,
        "penalty_second_submission": gc.penalty_second_submission,
        "penalty_third_submission": gc.penalty_third_submission,
        "false_positive_deduction": gc.false_positive_deduction,
        "grading_mode": gc.grading_mode,
        "max_submissions_per_analysis": gc.max_submissions_per_analysis,
        "final_score_strategy": gc.final_score_strategy,
        "passing_score": gc.passing_score,
    }


# ---- per-course grading config ----------------------------------------------------
@router.get("/courses/{course_id}/grading-config", response=GradingConfigOut)
def get_course_grading_config(request, course_id: int):
    """
    Read the grading configuration that applies to a course.

    Returns the course's own configuration if it has one, otherwise the global
    default (so the form is always populated with usable starting values).
    """
    if not getattr(request.user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    gc = GradingConfig.get_for_course(course)
    return _grading_config_payload(gc)


@router.put("/courses/{course_id}/grading-config", response=GradingConfigOut)
def update_course_grading_config(request, course_id: int, payload: GradingConfigOut):
    """Create or update a course's own grading configuration (admin)."""
    _admin_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course not found.")
    gc, _ = GradingConfig.objects.get_or_create(course=course)
    _apply_grading_payload(gc, payload)
    gc.save()
    logger.info("Admin %s updated grading config for course %s", request.user.username, course.name)
    return _grading_config_payload(gc)


@router.get("/app-settings", response=AppSettingsOut)
def get_app_settings(request):
    """Read global app settings (any authenticated user)."""
    if not getattr(request.user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    s = AppSettings.get_instance()
    return {
        "points_per_analysis": s.points_per_analysis,
        "analyses_per_course": s.analyses_per_course,
        "active_course_id": s.active_course_id,
        "backup_enabled": s.backup_enabled,
        "backup_interval_minutes": s.backup_interval_minutes,
        "backup_location": s.backup_location,
        "backup_keep": s.backup_keep,
    }


@router.put("/app-settings", response=AppSettingsOut)
def update_app_settings(request, payload: AppSettingsOut):
    """Update global app settings (admin)."""
    _admin_user(request)
    s = AppSettings.get_instance()
    s.points_per_analysis = payload.points_per_analysis
    s.analyses_per_course = payload.analyses_per_course
    s.active_course_id = payload.active_course_id
    s.backup_enabled = payload.backup_enabled
    s.backup_interval_minutes = max(1, payload.backup_interval_minutes)
    s.backup_location = payload.backup_location
    s.backup_keep = max(1, payload.backup_keep)
    s.save()
    logger.info("Admin %s updated app settings", request.user.username)
    return {
        "points_per_analysis": s.points_per_analysis,
        "analyses_per_course": s.analyses_per_course,
        "active_course_id": s.active_course_id,
        "backup_enabled": s.backup_enabled,
        "backup_interval_minutes": s.backup_interval_minutes,
        "backup_location": s.backup_location,
        "backup_keep": s.backup_keep,
    }


# ---- database backups ----------------------------------------------------------
@router.get("/database/backups", response=DatabaseStatusOut)
def database_backups(request):
    """Database section status: backend, backup settings, last runs, backup files (admin)."""
    _admin_user(request)
    return db_backup.get_status()


def _mark_backup_taken(filename: str) -> None:
    """Record a successful backup on the AppSettings singleton (fresh instance)."""
    s = AppSettings.get_instance()
    s.last_backup_at = datetime.now(UTC)
    s.last_backup_file = filename
    s.save(update_fields=["last_backup_at", "last_backup_file"])


@router.post("/database/backup", response=DatabaseStatusOut)
def database_backup_now(request):
    """Take a database backup immediately (admin)."""
    _admin_user(request)
    s = AppSettings.get_instance()
    try:
        result = db_backup.run_backup(db_backup.resolve_backup_location(s.backup_location), s.backup_keep)
    except db_backup.BackupError as exc:
        raise HttpError(400, str(exc)) from exc
    _mark_backup_taken(result["file"])
    logger.info("Admin %s took a database backup (%s)", request.user.username, result["file"])
    return db_backup.get_status()


@router.post("/database/restore", response=DatabaseStatusOut)
def database_restore(request, payload: DatabaseRestoreIn):
    """Restore the database from a backup file (admin)."""
    _admin_user(request)
    s = AppSettings.get_instance()
    try:
        result = db_backup.restore_backup(db_backup.resolve_backup_location(s.backup_location), payload.file)
    except db_backup.BackupError as exc:
        raise HttpError(400, str(exc)) from exc
    # restore_backup() closed the pooled connections (file swap), so re-fetch
    # the settings and build the response from fresh data.
    db_backup.mark_restored(result["file"])
    logger.info("Admin %s restored the database from %s", request.user.username, result["file"])
    return db_backup.get_status()
