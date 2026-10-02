"""
Admin endpoints: CRUD for analysis types, instances, assignments, grading config.

All mutating endpoints are admin-only and logged to the audit logger.
"""

from __future__ import annotations

import logging
from datetime import datetime

from analyses.api.schemas import (
    AnalysisInstanceIn,
    AnalysisTypeIn,
    AppSettingsOut,
    AssignmentIn,
    CourseIn,
    GradingConfigOut,
    RandomizeSubstancesIn,
    RandomizeSubstancesOut,
    RandomizeSubstancesStudentOut,
    StudentCourseAssignIn,
    StudentOut,
)
from analyses.models import AnalysisInstance, AnalysisType
from analyses.services import InsufficientIonsError, randomize_substances_for_announcement
from config.models import AppSettings, Course, GradingConfig
from ninja import Router
from ninja.errors import AuthenticationError, HttpError
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
@router.get("/students", response=list[StudentOut])
def list_students(request, course_id: int | None = None):
    """List students (admin), optionally filtered by their course."""
    _admin_user(request)
    qs = User.objects.filter(role=User.Role.STUDENT).select_related("course")
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    return [
        {
            "id": s.id,
            "username": s.username,
            "name": s.name or None,
            "course_id": s.course_id,
            "course_name": s.course.name if s.course else None,
            "is_active": s.is_active,
        }
        for s in qs
    ]


@router.put("/students/{student_id}/course", response=dict)
def assign_student_course(request, student_id: int, payload: StudentCourseAssignIn):
    """Assign a student to a course (or detach with ``course_id = null``) (admin)."""
    _admin_user(request)
    student = User.objects.filter(pk=payload.student_id, role=User.Role.STUDENT).first()
    if student is None:
        raise HttpError(404, "Student not found.")
    if payload.course_id is not None:
        course = Course.objects.filter(pk=payload.course_id).first()
        if course is None:
            raise HttpError(404, "Course not found.")
        student.course = course
    else:
        student.course = None
    student.save(update_fields=["course"])
    logger.info(
        "Admin %s set course for student %s to %s",
        request.user.username,
        student.username,
        payload.course_id,
    )
    return {"id": student.id, "username": student.username, "course_id": student.course_id}


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
    return {
        "points_per_correct_ion": gc.points_per_correct_ion,
        "penalty_second_submission": gc.penalty_second_submission,
        "penalty_third_submission": gc.penalty_third_submission,
        "false_positive_deduction": gc.false_positive_deduction,
        "grading_mode": gc.grading_mode,
        "max_submissions_per_analysis": gc.max_submissions_per_analysis,
        "final_score_strategy": gc.final_score_strategy,
    }


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
    """Copy the seven grading fields from ``payload`` onto ``gc`` (no save)."""
    gc.points_per_correct_ion = payload.points_per_correct_ion
    gc.penalty_second_submission = payload.penalty_second_submission
    gc.penalty_third_submission = payload.penalty_third_submission
    gc.false_positive_deduction = payload.false_positive_deduction
    gc.grading_mode = payload.grading_mode
    gc.max_submissions_per_analysis = payload.max_submissions_per_analysis
    gc.final_score_strategy = payload.final_score_strategy


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
    }


@router.put("/app-settings", response=AppSettingsOut)
def update_app_settings(request, payload: AppSettingsOut):
    """Update global app settings (admin)."""
    _admin_user(request)
    s = AppSettings.get_instance()
    s.points_per_analysis = payload.points_per_analysis
    s.analyses_per_course = payload.analyses_per_course
    s.active_course_id = payload.active_course_id
    s.save()
    logger.info("Admin %s updated app settings", request.user.username)
    return {
        "points_per_analysis": s.points_per_analysis,
        "analyses_per_course": s.analyses_per_course,
        "active_course_id": s.active_course_id,
    }
