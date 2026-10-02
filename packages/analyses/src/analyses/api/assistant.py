"""
Assistant-facing endpoints: course roster, per-student detail, statistics, CSV export.

An assistant may only see courses they are assigned to (``AssistantCourse`` M2M)
or, if they have staff privileges, all active courses.
"""

from __future__ import annotations

import csv
import io

from analyses.api.schemas import AnalysisSummary, AssistantCourseOut, AssistantRosterEntry
from analyses.models import AnalysisInstance
from config.models import GradingConfig
from django.http import HttpResponse
from ninja import Router
from ninja.errors import AuthenticationError, HttpError
from users.models import User

router = Router(tags=["assistant"])


def _assistant_user(request) -> User:
    """Return the request user if it is an assistant (or admin), else 401."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise AuthenticationError(401, "Authentication required.")
    if not (user.is_assistant or user.is_admin):
        raise AuthenticationError(403, "Assistant role required.")
    return user


def _visible_courses(user: User):
    """Courses the assistant may see: their M2M assignments, or all if admin."""
    if user.is_admin:
        from config.models import Course

        return Course.objects.filter(is_active=True).prefetch_related("students")
    return (
        user.assistant_courses.filter(course__is_active=True)
        .select_related("course")
        .prefetch_related("course__students")
    )


@router.get("/courses", response=list[AssistantCourseOut])
def list_courses(request):
    """All courses visible to the assistant with roster + statistics."""
    user = _assistant_user(request)
    courses = _visible_courses(user)
    out = []
    for entry in courses:
        # entry is a Course (admin) or AssistantCourse (assistant)
        course = entry.course if hasattr(entry, "course") else entry
        students = [
            AssistantRosterEntry(
                id=s.id,
                username=s.username,
                name=s.name or None,
                barcode=s.barcodes.filter(active=True).first().value
                if s.barcodes.filter(active=True).exists()
                else None,
                analyses=[
                    AnalysisSummary.from_instance(i)
                    for i in AnalysisInstance.objects.for_student(s)
                    if i.course_id == course.id or i.course is None
                ],
            )
            for s in course.students.all()
        ]
        instances = AnalysisInstance.objects.filter(course=course).prefetch_related("submissions")
        submitted = sum(1 for i in instances if i.submissions.exists())
        total = len(list(instances))
        scores = [i.score() for i in instances if i.score() is not None]
        stats = {
            "total_assignments": total,
            "submitted": submitted,
            "pending": total - submitted,
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
            "passing_score": int(GradingConfig.get_for_course(course).passing_score),
        }
        out.append(
            {
                "id": course.id,
                "name": course.name,
                "semester": course.semester,
                "is_active": course.is_active,
                "students": students,
                "stats": stats,
            }
        )
    return out


@router.get("/courses/{course_id}", response=AssistantCourseOut)
def course_detail(request, course_id: int):
    """Detail for one course (roster + statistics)."""
    user = _assistant_user(request)
    entry = next(
        (c for c in _visible_courses(user) if (c.course.id if hasattr(c, "course") else c.id) == course_id), None
    )
    if entry is None:
        raise HttpError(404, "Course not found.")
    course = entry.course if hasattr(entry, "course") else entry
    students = [
        AssistantRosterEntry(
            id=s.id,
            username=s.username,
            name=s.name or None,
            barcode=s.barcodes.filter(active=True).first().value if s.barcodes.filter(active=True).exists() else None,
            analyses=[
                AnalysisSummary.from_instance(i)
                for i in AnalysisInstance.objects.for_student(s)
                if i.course_id == course.id or i.course is None
            ],
        )
        for s in course.students.all()
    ]
    instances = AnalysisInstance.objects.filter(course=course).prefetch_related("submissions")
    submitted = sum(1 for i in instances if i.submissions.exists())
    total = len(list(instances))
    scores = [i.score() for i in instances if i.score() is not None]
    return {
        "id": course.id,
        "name": course.name,
        "semester": course.semester,
        "is_active": course.is_active,
        "students": students,
        "stats": {
            "total_assignments": total,
            "submitted": submitted,
            "pending": total - submitted,
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        },
    }


@router.get("/courses/{course_id}/substance-overview")
def course_substance_overview(request, course_id: int, samples_per_analysis: int | None = None):
    """
    Substance preparation overview for one course.

    The course's per-student sheets are grouped by (announcement number,
    correct ion set), i.e. by sample composition. For every group, lists the
    substances that share at least one of the group's correct ions (the same
    convention as the student reference list, but based on the actual sample
    composition instead of the possible-ion set). ``sample_count`` is the
    number of prepared samples per group: by default the number of sheets in
    the group, overridable via the ``samples_per_analysis`` query parameter.
    The per-substance totals aggregate the number of substance units the
    course needs in total.
    """
    user = _assistant_user(request)
    entry = next(
        (c for c in _visible_courses(user) if (c.course.id if hasattr(c, "course") else c.id) == course_id), None
    )
    if entry is None:
        raise HttpError(404, "Course not found.")
    course = entry.course if hasattr(entry, "course") else entry

    from substances.api.schemas import ion_to_schema, substance_to_schema
    from substances.models import Ion, Substance

    # Instances are per-student sheets; the preparation unit is the *composition*.
    # Group by (number, correct ion set) so identical announcements collapse into
    # one row, while differing compositions within a number stay separate.
    instances = (
        AnalysisInstance.objects.filter(course=course).order_by("number").prefetch_related("correct_ions", "type")
    )
    groups: dict[tuple[int, frozenset[int]], dict] = {}
    for inst in instances:
        key = (inst.number, frozenset(inst.correct_ions.values_list("id", flat=True)))
        group = groups.setdefault(
            key,
            {"number": inst.number, "type_name": inst.type.name, "correct_ids": set(key[1]), "sheets": 0},
        )
        group["sheets"] += 1

    analyses = []
    totals: dict[int, dict] = {}
    total_units = 0
    for key in sorted(groups):
        group = groups[key]
        correct_ids = sorted(group["correct_ids"])
        substances = (
            list(Substance.objects.filter(ions__id__in=correct_ids).distinct().prefetch_related("ions"))
            if correct_ids
            else []
        )
        samples = samples_per_analysis if (samples_per_analysis or 0) > 0 else group["sheets"]
        correct_ions = list(Ion.objects.filter(id__in=correct_ids).order_by("symbol"))
        for s in substances:
            t = totals.setdefault(
                s.id,
                {"id": s.id, "name": s.name, "formula": s.formula, "count": 0, "used_in_analyses": 0},
            )
            t["count"] += samples
            t["used_in_analyses"] += 1
        total_units += samples * len(substances)
        analyses.append(
            {
                "number": group["number"],
                "type": group["type_name"],
                "student_count": group["sheets"],
                "sample_count": samples,
                "correct_ions": [ion_to_schema(i) for i in correct_ions],
                "substances": [substance_to_schema(s) for s in substances],
            }
        )
    totals_list = sorted(totals.values(), key=lambda t: (-t["count"], t["name"].lower()))
    return {
        "course_id": course.id,
        "course_name": course.name,
        "samples_per_analysis": samples_per_analysis,
        "analyses": analyses,
        "totals": totals_list,
        "total_units": total_units,
        "distinct_substances": len(totals_list),
    }


@router.get("/students/{student_id}/submissions")
def student_submissions(request, student_id: int):
    """All of a student's submissions across their analyses (with the correct answer key)."""
    user = _assistant_user(request)
    visible = [c.course if hasattr(c, "course") else c for c in _visible_courses(user)]
    student = User.objects.filter(pk=student_id, course__in=visible).first()
    if student is None:
        raise HttpError(404, "Student not found in a visible course.")
    instances = AnalysisInstance.objects.for_student(student).prefetch_related(
        "submissions", "submissions__selected_ions", "correct_ions", "type"
    )
    from substances.api.schemas import ion_to_schema

    out = []
    for inst in instances:
        from substances.models import Substance  # noqa: F401  (kept for import clarity)

        out.append(
            {
                "student": student.username,
                "analysis": str(inst),
                "analysis_id": inst.id,
                "correct_ions": [ion_to_schema(i) for i in inst.correct_ions.all()],
                "submissions": [
                    {
                        "id": s.id,
                        "submission_number": s.submission_number,
                        "submitted_at": s.submitted_at.isoformat(),
                        "score": s.score,
                        "correct_count": s.correct_count,
                        "wrong_count": s.wrong_count,
                        "missing_count": s.missing_count,
                        "penalty": s.penalty,
                        "selected_ions": [ion_to_schema(i) for i in s.selected_ions.all()],
                    }
                    for s in inst.submissions.all()
                ],
            }
        )
    return out


@router.get("/courses/{course_id}/export/csv", response=None)
def course_csv_export(request, course_id: int):
    """CSV export of all submissions for one course (audit-friendly)."""
    user = _assistant_user(request)
    entry = next(
        (c for c in _visible_courses(user) if (c.course.id if hasattr(c, "course") else c.id) == course_id), None
    )
    if entry is None:
        raise HttpError(404, "Course not found.")
    course = entry.course if hasattr(entry, "course") else entry

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "student_username",
            "student_name",
            "analysis_id",
            "analysis_type",
            "number",
            "submission_number",
            "submitted_at",
            "selected_ions",
            "correct_ions",
            "correct_count",
            "wrong_count",
            "missing_count",
            "score",
            "penalty",
            "ideal_score",
        ]
    )
    instances = (
        AnalysisInstance.objects.filter(assignments__course=course)
        .distinct()
        .prefetch_related("submissions", "submissions__selected_ions", "correct_ions", "type", "assignments__student")
    )
    for inst in instances:
        student_names = ", ".join(a.student.username for a in inst.assignments.filter(course=course))
        for s in inst.submissions.all():
            selected = ", ".join(i.symbol for i in s.selected_ions.all())
            correct = ", ".join(i.symbol for i in inst.correct_ions.all())
            writer.writerow(
                [
                    student_names,
                    "",
                    inst.id,
                    inst.type.name,
                    inst.number,
                    s.submission_number,
                    s.submitted_at.isoformat(),
                    selected,
                    correct,
                    s.correct_count,
                    s.wrong_count,
                    s.missing_count,
                    s.score,
                    s.penalty,
                    s.ideal_score,
                ]
            )
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="course_{course.id}_submissions.csv"'
    return response
