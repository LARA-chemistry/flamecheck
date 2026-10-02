"""
CSV import of a set of analyses per course (admin).

An admin uploads a CSV that defines the course's analyses: each row references
an analysis type by name and an announcement number, carries an optional
submission window (falling back to the type's default window), and may list
the students to assign, identified by their Labspace IDs. Existing
(course, type, number) instances are reused, and existing assignments are
skipped, so re-uploading a corrected file is safe.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime

from config.models import Course
from django.db import transaction
from django.utils import timezone
from users.models import StudentAssignment, User

from analyses.models import AnalysisInstance, AnalysisType

#: Column order of the import file / template.
TEMPLATE_HEADER = ["type", "number", "window_start", "window_end", "labspace_ids"]

#: Largest accepted upload (bytes); the file is tiny by design.
MAX_UPLOAD_BYTES = 200_000


class CsvImportError(Exception):
    """Raised when a CSV cannot be applied; carries all collected issues."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


@dataclass(frozen=True)
class CsvImportSummary:
    """Outcome of a successful import."""

    course_id: int
    rows: int
    analyses_created: int
    analyses_reused: int
    students_assigned: int
    assignments_skipped: int


def render_template() -> str:
    """
    Render the CSV template: a header plus one example row per analysis type.

    Window columns are left empty so rows inherit the type's default window;
    labspace_ids is left empty for the admin to fill in.
    """
    lines = [",".join(TEMPLATE_HEADER)]
    types = list(AnalysisType.objects.order_by("name"))
    if not types:
        lines.append("Example type,1,,,")
        return "\n".join(lines) + "\n"
    for number, type_ in enumerate(types, start=1):
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="\n").writerow([type_.name, number, "", "", ""])
        lines.append(buffer.getvalue().rstrip("\n"))
    return "\n".join(lines) + "\n"


def _split_ids(raw: str) -> list[str]:
    """Split a comma/semicolon-separated ID list into trimmed, de-duplicated parts."""
    seen: set[str] = set()
    parts: list[str] = []
    for chunk in re.split(r"[,;]", raw or ""):
        chunk = chunk.strip()
        if chunk and chunk not in seen:
            seen.add(chunk)
            parts.append(chunk)
    return parts


def _parse_iso(value: str, column: str, row_no: int, issues: list[str]) -> datetime | None:
    """Parse an optional ISO-8601 datetime cell ('' means 'use the type default')."""
    value = value.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        issues.append(f"Row {row_no}: invalid {column} value {value!r} (expected ISO 8601, e.g. 2026-10-01T08:00:00).")
        return None
    if parsed.tzinfo is None:
        # Naive cells are taken in the project's default timezone so they can
        # be compared with the (aware) type default windows.
        parsed = timezone.make_aware(parsed)
    return parsed


@dataclass(frozen=True)
class _Row:
    """A validated CSV row, ready to apply."""

    number: int
    type_: AnalysisType
    window_start: datetime | None
    window_end: datetime | None
    student_ids: list[str]


def import_analyses_csv(course: Course, raw: bytes) -> CsvImportSummary:
    """
    Validate and apply an analyses CSV for ``course``.

    Every row is validated first; if any row has issues nothing is written and
    :class:`CsvImportError` is raised with the full list of issues. On success,
    (course, type, number) instances are created or reused and the listed
    students (by Labspace ID) are assigned to them.

    Args:
        course: The course the analyses belong to.
        raw: The raw CSV bytes (UTF-8, optional BOM).

    Returns:
        CsvImportSummary: Counts of created/reused analyses and assignments.

    Raises:
        CsvImportError: If the file has structural or referential issues.

    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvImportError(["The file is not valid UTF-8 text."]) from None

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CsvImportError(["The file is empty."])
    headers = [(h or "").strip().lower() for h in reader.fieldnames]
    missing = [col for col in ("type", "number") if col not in headers]
    if missing:
        raise CsvImportError([f"Missing required column(s): {', '.join(missing)}."])

    issues: list[str] = []
    rows: list[_Row] = []
    enrolled = {u.labspace_id: u for u in User.objects.filter(course=course, role=User.Role.STUDENT) if u.labspace_id}
    any_labspace = {u.labspace_id: u for u in User.objects.exclude(labspace_id="") if u.labspace_id}

    for row_no, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "") for k, v in raw_row.items() if k is not None}
        type_name = row.get("type", "").strip()
        if not type_name:
            issues.append(f"Row {row_no}: 'type' is required.")
            continue
        type_ = AnalysisType.objects.filter(name__iexact=type_name).first()
        if type_ is None:
            issues.append(f"Row {row_no}: unknown analysis type {type_name!r}.")
            continue

        number_raw = row.get("number", "").strip()
        try:
            number = int(number_raw)
            if number < 1:
                raise ValueError
        except ValueError:
            issues.append(f"Row {row_no}: 'number' must be a positive integer (got {number_raw!r}).")
            continue

        window_start = _parse_iso(row.get("window_start", ""), "window_start", row_no, issues)
        window_end = _parse_iso(row.get("window_end", ""), "window_end", row_no, issues)
        if window_start is None:
            window_start = type_.default_window_start
        if window_end is None:
            window_end = type_.default_window_end
        if window_start is None or window_end is None:
            issues.append(
                f"Row {row_no}: {type_name!r} has no window and the type has no default window "
                "(set window_start/window_end)."
            )
        elif window_end <= window_start:
            issues.append(f"Row {row_no}: window_end must be after window_start.")

        student_ids = _split_ids(row.get("labspace_ids", ""))
        for sid in student_ids:
            if sid in enrolled:
                continue
            if sid in any_labspace:
                issues.append(f"Row {row_no}: Labspace ID {sid!r} does not belong to a student in this course.")
            else:
                issues.append(f"Row {row_no}: unknown Labspace ID {sid!r}.")

        rows.append(
            _Row(
                number=number,
                type_=type_,
                window_start=window_start,
                window_end=window_end,
                student_ids=student_ids,
            )
        )

    if not rows:
        if not issues:
            issues.append("The file contains no data rows.")
        raise CsvImportError(issues)
    if issues:
        raise CsvImportError(issues)

    # Apply atomically: create/reuse instances, then assign students.
    created = reused = assigned = skipped = 0
    with transaction.atomic():
        for row in rows:
            existing = AnalysisInstance.objects.filter(course=course, type=row.type_, number=row.number).first()
            if existing is not None:
                instance = existing
                reused += 1
            else:
                instance = AnalysisInstance.objects.create(
                    type=row.type_,
                    course=course,
                    number=row.number,
                    window_start=row.window_start,
                    window_end=row.window_end,
                )
                created += 1

            for sid in row.student_ids:
                student = enrolled[sid]
                if StudentAssignment.objects.filter(student=student, instance=instance).exists():
                    skipped += 1
                    continue
                conflict = StudentAssignment.objects.filter(course=course, student=student, number=row.number).exclude(
                    instance=instance
                )
                if conflict.exists():
                    raise CsvImportError(
                        [
                            f"Labspace ID {sid!r}: the student already has a different analysis "
                            f"for number #{row.number} in this course."
                        ]
                    )
                StudentAssignment.objects.create(course=course, student=student, instance=instance, number=row.number)
                assigned += 1

    return CsvImportSummary(
        course_id=course.id,
        rows=len(rows),
        analyses_created=created,
        analyses_reused=reused,
        students_assigned=assigned,
        assignments_skipped=skipped,
    )
