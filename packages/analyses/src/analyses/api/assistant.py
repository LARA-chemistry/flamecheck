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
