"""
CSV import of a set of analyses per course (admin).

An admin uploads a CSV that defines the course's analyses: each row references
an analysis type by name, an announcement number, an optional submission window
(falling back to the type's default window), the student to assign (by their
Labspace ID), and the analysis *composition* — the salts/compounds present,
listed with the comma as the separator. The composition becomes the per-student
answer key: the union of the ions each listed substance provides is stored on
the instance as ``correct_ions``, and the substances themselves are recorded as
``assigned_substances``.

Because the number of salts depends on the analysis type, the file uses ``;``
as the column separator and ```` `,` ```` as the substance separator within the
composition cell, so a cell may contain commas without needing quoting.

Existing (student, course, number) assignments are reused and existing
assignments are skipped, so re-uploading a corrected file is safe.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime

from config.models import Course
from django.db import transaction
from django.utils import timezone
from substances.models import Ion, Substance
from users.models import StudentAssignment, User

from analyses.models import AnalysisInstance, AnalysisType

#: Column order of the import file / template.
TEMPLATE_HEADER = ["type", "number", "window_start", "window_end", "labspace_id", "substances"]

#: The column separator for the import file (so a composition cell may hold commas).
FIELD_SEP = ";"

#: The separator between individual substances within the composition cell.
SUBSTANCE_SEP = ","

#: Largest accepted upload (bytes); the file is small by design.
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
    compositions_applied: int


@dataclass(frozen=True)
class _Row:
    """A validated CSV row, ready to apply."""

    number: int
    type_: AnalysisType
    window_start: datetime | None
    window_end: datetime | None
    labspace_id: str
    substances: tuple[Substance, ...] = field(default=())


def render_template() -> str:
    """
    Render the CSV template: a header plus one example row per analysis type.

    Window columns are left empty so rows inherit the type's default window;
    the labspace_id and substances columns are left empty for the admin to
    fill in (one row per student).
    """
    lines = [FIELD_SEP.join(TEMPLATE_HEADER)]
    types = list(AnalysisType.objects.order_by("name"))
    if not types:
        lines.append("Example type;1;;;;")
        return "\n".join(lines) + "\n"
    for number, type_ in enumerate(types, start=1):
        lines.append(f"{type_.name};{number};;;;")
    return "\n".join(lines) + "\n"


def _split_substances(raw: str) -> list[str]:
    """Split a composition cell (```` `,` ````-separated) into trimmed, de-duplicated parts."""
    seen: set[str] = set()
    parts: list[str] = []
    for chunk in raw.split(SUBSTANCE_SEP):
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


def _load_substance_index() -> dict[str, Substance]:
    """
    Build a case-insensitive lookup from name / formula / synonym → substance.

    A substance is findable by its common name, its chemical formula, or any of
    its listed synonyms, all matched case-insensitively.
    """
    index: dict[str, Substance] = {}
    for sub in Substance.objects.prefetch_related("ions").order_by("id"):
        keys = {sub.name}
        if sub.formula:
            keys.add(sub.formula)
        keys.update(sub.synonyms or [])
        for key in keys:
            norm = key.strip().lower()
            if norm:
                index.setdefault(norm, sub)
    return index


def _resolve_substances(
    names: list[str],
    index: dict[str, Substance],
    row_no: int,
    issues: list[str],
) -> list[Substance]:
    """Resolve composition names to substances, collecting issues for unknown ones."""
    resolved: list[Substance] = []
    seen: set[int] = set()
    for name in names:
        sub = index.get(name.strip().lower())
        if sub is None:
            issues.append(f"Row {row_no}: unknown substance {name!r} (match by name, formula or synonym).")
            continue
        if sub.id not in seen:
            seen.add(sub.id)
            resolved.append(sub)
    return resolved


def _composition_ions(substances: list[Substance]) -> list[Ion]:
    """The union of the ions every listed substance provides (the answer key)."""
    ions: list[Ion] = []
    seen: set[int] = set()
    for sub in substances:
        for ion in sub.ions.all():
            if ion.id not in seen:
                seen.add(ion.id)
                ions.append(ion)
    return ions


def import_analyses_csv(course: Course, raw: bytes) -> CsvImportSummary:
    """
    Validate and apply an analyses CSV for ``course``.

    Every row is validated first; if any row has issues nothing is written and
    :class:`CsvImportError` is raised with the full list of issues. On success,
    a (student, course, number) analysis instance is created or reused, the
    row's composition is applied as its answer key (``correct_ions``) and
    reference substances (``assigned_substances``), and the student is assigned
    to it.

    Args:
        course: The course the analyses belong to.
        raw: The raw CSV bytes (UTF-8, optional BOM). Columns are separated by
            ``;`` and the composition cell's substances by ``,``.

    Returns:
        CsvImportSummary: Counts of created/reused analyses, assignments and
            compositions applied.

    Raises:
        CsvImportError: If the file has structural or referential issues.

    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvImportError(["The file is not valid UTF-8 text."]) from None

    stream = io.StringIO(text)
    first_line = stream.readline()
    if not first_line.strip():
        raise CsvImportError(["The file is empty."])
    stream.seek(0)

    reader = csv.reader(stream, delimiter=FIELD_SEP)
    header_cells = next(reader, None)
    if header_cells is None:
        raise CsvImportError(["The file is empty."])
    headers = [(h or "").strip().lower() for h in header_cells]
    missing = [col for col in ("type", "number") if col not in headers]
    if missing:
        raise CsvImportError([f"Missing required column(s): {', '.join(missing)}."])
    has_substances = "substances" in headers

    issues: list[str] = []
    rows: list[_Row] = []
    enrolled = {u.labspace_id: u for u in User.objects.filter(course=course, role=User.Role.STUDENT) if u.labspace_id}
    any_labspace = {u.labspace_id: u for u in User.objects.exclude(labspace_id="") if u.labspace_id}
    substance_index = _load_substance_index()

    def _cell(cells: list[str], column: str) -> str:
        """Return ``cells[i]`` for ``column`` (empty string when the column is absent)."""
        try:
            return cells[headers.index(column)]
        except (ValueError, IndexError):
            return ""

    for row_no, cells in enumerate(reader, start=2):
        if not cells or all((c or "").strip() == "" for c in cells):
            continue  # skip blank lines
        type_name = _cell(cells, "type").strip()
        if not type_name:
            issues.append(f"Row {row_no}: 'type' is required.")
            continue
        type_ = AnalysisType.objects.filter(name__iexact=type_name).first()
        if type_ is None:
            issues.append(f"Row {row_no}: unknown analysis type {type_name!r}.")
            continue

        number_raw = _cell(cells, "number").strip()
        try:
            number = int(number_raw)
            if number < 1:
                raise ValueError
        except ValueError:
            issues.append(f"Row {row_no}: 'number' must be a positive integer (got {number_raw!r}).")
            continue

        window_start = _parse_iso(_cell(cells, "window_start"), "window_start", row_no, issues)
        window_end = _parse_iso(_cell(cells, "window_end"), "window_end", row_no, issues)
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

        sid = _cell(cells, "labspace_id").strip()
        if sid:
            if sid in enrolled:
                pass
            elif sid in any_labspace:
                issues.append(f"Row {row_no}: Labspace ID {sid!r} does not belong to a student in this course.")
            else:
                issues.append(f"Row {row_no}: unknown Labspace ID {sid!r}.")

        substance_names = _split_substances(_cell(cells, "substances")) if has_substances else []
        substances = _resolve_substances(substance_names, substance_index, row_no, issues)

        rows.append(
            _Row(
                number=number,
                type_=type_,
                window_start=window_start,
                window_end=window_end,
                labspace_id=sid,
                substances=tuple(substances),
            )
        )

    if not rows:
        if not issues:
            issues.append("The file contains no data rows.")
        raise CsvImportError(issues)
    if issues:
        raise CsvImportError(issues)

    # Apply atomically: create/reuse instances, apply compositions, assign students.
    # A row with no labspace_id defines an unassigned instance (e.g. a default
    # composition); a row with a labspace_id creates/reuses a per-student
    # instance and assigns that student.
    created = reused = assigned = skipped = compositions = 0
    with transaction.atomic():
        for row in rows:
            student = enrolled.get(row.labspace_id)
            if student is not None:
                existing = AnalysisInstance.objects.filter(
                    course=course, type=row.type_, number=row.number, assignments__student=student
                ).first()
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
            else:
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

            if row.substances:
                ions = _composition_ions(list(row.substances))
                instance.correct_ions.set([i.id for i in ions])
                instance.assigned_substances.set([s.id for s in row.substances])
                compositions += 1

            if student is not None:
                if StudentAssignment.objects.filter(student=student, instance=instance).exists():
                    skipped += 1
                else:
                    conflict = StudentAssignment.objects.filter(
                        course=course, student=student, number=row.number
                    ).exclude(instance=instance)
                    if conflict.exists():
                        raise CsvImportError(
                            [
                                f"Labspace ID {row.labspace_id!r}: the student already has a different "
                                f"analysis for number #{row.number} in this course."
                            ]
                        )
                    StudentAssignment.objects.create(
                        course=course, student=student, instance=instance, number=row.number
                    )
                    assigned += 1

    return CsvImportSummary(
        course_id=course.id,
        rows=len(rows),
        analyses_created=created,
        analyses_reused=reused,
        students_assigned=assigned,
        assignments_skipped=skipped,
        compositions_applied=compositions,
    )
