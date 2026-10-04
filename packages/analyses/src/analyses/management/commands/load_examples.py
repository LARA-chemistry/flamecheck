"""
Load the example/demo dataset into the database.

This command populates a complete, immediately-usable demo environment:

* the ion / substance reference catalog (via :cmd:`import_catalog`),
* courses (one per specialisation track),
* users (admin, assistants, students) with hashed passwords and student barcodes,
* assistant → course links,
* analysis types (each with a *possible* ion set),
* analysis instances with *correct* ion sets and time windows computed
  relative to "now" (so the demo always contains open / too-early / too-late
  windows),
* student → instance assignments,
* the singleton :class:`~config.models.GradingConfig` and
  :class:`~config.models.AppSettings`,
* a few pre-seeded submissions (graded through the real
  :meth:`~analyses.models.AnalysisInstance.submit` business logic).

Design note: an :class:`~analyses.models.AnalysisInstance` represents one
*sheet* and the per-instance counters (submission limit, retry ordinal) are
not per-student, so each student is assigned their **own dedicated instance**
for every announcement. The ``analysis_instances.json`` file therefore holds
per-course *announcement templates* which this command fans out into one
instance per assigned student.

The command is idempotent: re-running it refreshes the data without creating
duplicates. Pass ``--reset`` to wipe the analyses domain and the sample
users/courses first (useful after experimenting).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config.models import AppSettings, AssistantCourse, Course, GradingConfig
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from substances.models import Ion
from users.models import StudentAssignment, StudentBarcode, User

from analyses.models import AnalysisInstance, AnalysisType, Submission


def _load_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON dataset file."""
    return json.loads(path.read_text(encoding="utf-8"))


class Command(BaseCommand):
    """Load the example dataset from a directory of JSON files."""

    help = "Load the example/demo dataset (courses, users, analyses, submissions) into the database."

    def add_arguments(self, parser: Any) -> None:
        """Register the command-line options (--dir, --reset)."""
        default_dir = Path(settings.BASE_DIR) / "examples" / "datasets"
        parser.add_argument(
            "--dir",
            type=Path,
            default=default_dir,
            help="Directory containing the example JSON datasets (default: <BASE_DIR>/examples/datasets).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Wipe the analyses domain and the sample users/courses before loading.",
        )

    # -- entry point ---------------------------------------------------------
    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        """Load the example dataset (optionally after a reset)."""
        data_dir: Path = options["dir"]
        if not data_dir.is_dir():
            raise CommandError(f"Dataset directory does not exist: {data_dir}")

        data = {
            "courses": _load_json(data_dir / "courses.json")["courses"],
            "users": _load_json(data_dir / "users.json"),
            "assistant_courses": _load_json(data_dir / "assistant_courses.json")["assistant_courses"],
            "types": _load_json(data_dir / "analysis_types.json")["types"],
            "instances": _load_json(data_dir / "analysis_instances.json")["instances"],
            "assignments": _load_json(data_dir / "assignments.json")["assignments"],
            "submissions": _load_json(data_dir / "submissions.json")["submissions"],
            "grading_config": _load_json(data_dir / "grading_config.json"),
            "app_settings": _load_json(data_dir / "app_settings.json"),
        }

        if options["reset"]:
            self._reset(data)

        # Reference catalog (ions + substances) first, so symbols resolve.
        call_command("import_catalog", verbosity=0)
        self._ensure_ions(data)

        courses = self._load_courses(data["courses"])
        users = self._load_users(data["users"])
        self._load_assistant_courses(data["assistant_courses"], users, courses)
        types = self._load_types(data["types"])
        templates = self._load_templates(data["instances"], types, courses)
        student_instances = self._load_assignments(data["assignments"], users, templates)
        self._load_singletons(data["grading_config"], data["app_settings"], courses)
        self._load_submissions(data["submissions"], users, student_instances)

        self._print_summary(data, courses, users, templates, student_instances)

    # -- reset ---------------------------------------------------------------
    def _reset(self, data: dict[str, Any]) -> None:
        """Wipe the analyses domain and the sample users/courses."""
        usernames = [u["username"] for u in data["users"]["users"]]
        course_names = [c["name"] for c in data["courses"]]
        Submission.objects.all().delete()
        StudentAssignment.objects.all().delete()
        AnalysisInstance.objects.all().delete()
        AnalysisType.objects.all().delete()
        AssistantCourse.objects.all().delete()
        StudentBarcode.objects.all().delete()
        User.objects.filter(username__in=usernames).delete()
        Course.objects.filter(name__in=course_names).delete()
        self.stdout.write(self.style.WARNING("Reset: cleared analyses domain and sample users/courses."))

    # -- ions ----------------------------------------------------------------
    def _ensure_ions(self, data: dict[str, Any]) -> None:
        """Verify every ion symbol referenced by the dataset exists in the catalog."""
        symbols: set[str] = set()
        for t in data["types"]:
            symbols.update(t.get("possible_ions", []))
        for inst in data["instances"]:
            symbols.update(inst.get("correct_ions", []))
        for sub in data["submissions"]:
            symbols.update(sub.get("selected_ions", []))
        missing = symbols.difference(Ion.objects.values_list("symbol", flat=True))
        if missing:
            raise CommandError(f"Ion symbol(s) not present in catalog: {sorted(missing)}")

    # -- courses -------------------------------------------------------------
    def _load_courses(self, rows: list[dict[str, Any]]) -> dict[str, Course]:
        """Create/update courses; returns a name → course map."""
        result: dict[str, Course] = {}
        for row in rows:
            course, _ = Course.objects.get_or_create(
                name=row["name"],
                defaults={
                    "semester": row.get("semester", ""),
                    "track": row.get("track", ""),
                    "is_active": row.get("is_active", True),
                },
            )
            result[course.name] = course
        return result

    # -- users ---------------------------------------------------------------
    def _load_users(self, payload: dict[str, Any]) -> dict[str, User]:
        """Create/update users (hashed passwords) and student barcodes."""
        default_password: str = payload.get("default_password", "changeme")
        result: dict[str, User] = {}
        for row in payload["users"]:
            username = row["username"]
            is_admin = row.get("role") == "admin"
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User.objects.create_user(
                    username=username,
                    email=row.get("email", ""),
                    password=default_password,
                )
            # Always sync the password + profile fields (idempotent).
            user.set_password(default_password)
            user.email = row.get("email", "")
            # Prefer explicit first/last; fall back to splitting a legacy "name".
            first_name = row.get("first_name", "")
            last_name = row.get("last_name", "")
            if not first_name and not last_name:
                parts = str(row.get("name", "")).strip().split(None, 1)
                first_name = parts[0] if parts else ""
                last_name = parts[1] if len(parts) > 1 else ""
            user.first_name = first_name
            user.last_name = last_name
            user.role = row.get("role", User.Role.STUDENT)
            user.matriculation_no = row.get("matriculation_no", "")
            user.lab = row.get("lab", "")
            user.labspace_id = row.get("labspace_id", "")
            if is_admin:
                user.is_staff = True
                user.is_superuser = True
            user.save()

            course_name = row.get("course")
            if course_name:
                course = Course.objects.filter(name=course_name).first()
                user.course = course
                user.save(update_fields=["course"])

            barcode = row.get("barcode")
            if barcode:
                StudentBarcode.objects.update_or_create(
                    value=barcode,
                    defaults={"student": user, "active": True},
                )
            result[username] = user
        return result

    # -- assistant courses ---------------------------------------------------
    def _load_assistant_courses(
        self,
        rows: list[dict[str, Any]],
        users: dict[str, User],
        courses: dict[str, Course],
    ) -> None:
        for row in rows:
            assistant = users.get(row["assistant"])
            course = courses.get(row["course"])
            if assistant is None or course is None:
                continue
            AssistantCourse.objects.get_or_create(assistant=assistant, course=course)

    # -- analysis types ------------------------------------------------------
    def _load_types(self, rows: list[dict[str, Any]]) -> dict[str, AnalysisType]:
        """Create/update analysis types; returns a name → type map."""
        result: dict[str, AnalysisType] = {}
        for row in rows:
            analysis_type, _ = AnalysisType.objects.get_or_create(
                name=row["name"],
                defaults={"description": row.get("description", "")},
            )
            analysis_type.description = row.get("description", "")
            analysis_type.save()
            ions = Ion.objects.filter(symbol__in=row.get("possible_ions", [])).values_list("id", flat=True)
            analysis_type.possible_ions.set(ions)
            result[analysis_type.name] = analysis_type
        return result

    # -- announcement templates ----------------------------------------------
    def _load_templates(
        self,
        rows: list[dict[str, Any]],
        types: dict[str, AnalysisType],
        courses: dict[str, Course],
    ) -> dict[tuple[str, int], dict[str, Any]]:
        """
        Resolve announcement templates; returns a (course name, number) → template map.

        A template describes one *announcement* of a course (its type, the
        correct ion set, and the time window as offsets from "now"). It is not
        stored directly: the assignment step fans it out into one dedicated
        :class:`AnalysisInstance` per assigned student.
        """
        now: datetime = timezone.now().replace(microsecond=0)
        result: dict[tuple[str, int], dict[str, Any]] = {}
        for row in rows:
            course = courses.get(row.get("course", ""))
            if course is None:
                raise CommandError(f"Unknown course in analysis_instances: {row.get('course')!r}")
            number = int(row["number"])
            if (course.name, number) in result:
                raise CommandError(f"Duplicate announcement: course {course.name!r} already has a number {number}.")
            result[(course.name, number)] = {
                "type": types[row["type"]],
                "course": course,
                "number": number,
                "correct_ion_ids": list(
                    Ion.objects.filter(symbol__in=row.get("correct_ions", [])).values_list("id", flat=True)
                ),
                "window_start": now + timedelta(minutes=int(row["window_start_offset_minutes"])),
                "window_end": now + timedelta(minutes=int(row["window_end_offset_minutes"])),
            }
        return result

    # -- assignments (fan-out per student) ------------------------------------
    def _load_assignments(
        self,
        rows: list[dict[str, Any]],
        users: dict[str, User],
        templates: dict[tuple[str, int], dict[str, Any]],
    ) -> dict[tuple[str, str, int], AnalysisInstance]:
        """
        Give every assigned student their own instance per announcement.

        Returns a (student username, course name, number) → instance map.
        Idempotent: an existing assignment for (student, course, number) is
        reused and its instance refreshed.
        """
        result: dict[tuple[str, str, int], AnalysisInstance] = {}
        for row in rows:
            course_name: str = row["course"]
            for student_username in row["students"]:
                student = users.get(student_username)
                if student is None:
                    raise CommandError(f"Unknown student in assignments: {student_username!r}")
                for number in row["numbers"]:
                    number = int(number)
                    template = templates.get((course_name, number))
                    if template is None:
                        raise CommandError(f"No announcement template for course {course_name!r} number {number}.")
                    existing = StudentAssignment.objects.filter(
                        student=student, course=template["course"], number=number
                    ).first()
                    if existing is not None:
                        instance = existing.instance
                    else:
                        instance = AnalysisInstance.objects.create(
                            type=template["type"],
                            course=template["course"],
                            number=number,
                            window_start=template["window_start"],
                            window_end=template["window_end"],
                        )
                        StudentAssignment.objects.create(
                            student=student,
                            instance=instance,
                            course=template["course"],
                            number=number,
                        )
                    instance.window_start = template["window_start"]
                    instance.window_end = template["window_end"]
                    instance.save(update_fields=["window_start", "window_end"])
                    instance.correct_ions.set(template["correct_ion_ids"])
                    result[(student.username, course_name, number)] = instance
        return result

    # -- singletons ----------------------------------------------------------
    def _load_singletons(
        self,
        grading: dict[str, Any],
        app_settings: dict[str, Any],
        courses: dict[str, Course],
    ) -> None:
        config = GradingConfig.get_instance()
        for field, value in grading.items():
            setattr(config, field, value)
        config.save()

        app_settings_row = AppSettings.get_instance()
        app_settings_row.points_per_analysis = int(app_settings.get("points_per_analysis", 10))
        app_settings_row.analyses_per_course = int(app_settings.get("analyses_per_course", 3))
        active_name = app_settings.get("active_course")
        app_settings_row.active_course = courses.get(active_name) if active_name else None
        app_settings_row.save()

    # -- pre-seeded submissions ----------------------------------------------
    def _load_submissions(
        self,
        rows: list[dict[str, Any]],
        users: dict[str, User],
        student_instances: dict[tuple[str, str, int], AnalysisInstance],
    ) -> None:
        """Create pre-seeded submissions through the real submit() business logic."""
        for row in rows:
            student = users.get(row["student"])
            instance = student_instances.get((row["student"], row["course"], int(row["number"])))
            if student is None or instance is None:
                self.stdout.write(self.style.WARNING(f"  skip submission: unknown student/instance for {row}"))
                continue
            ion_ids = list(Ion.objects.filter(symbol__in=row.get("selected_ions", [])).values_list("id", flat=True))
            # submit() is idempotent per idempotency_key and enforces the window.
            try:
                submission = instance.submit(student, ion_ids, idempotency_key=row["idempotency_key"])
            except (ValidationError, PermissionDenied) as exc:
                self.stdout.write(self.style.WARNING(f"  skip submission {student.username} → {instance}: {exc}"))
                continue
            self.stdout.write(
                f"  submission: {student.username} → {instance}  score={submission.score} "
                f"#{submission.submission_number}"
            )

    # -- summary -------------------------------------------------------------
    def _print_summary(
        self,
        data: dict[str, Any],
        courses: dict[str, Course],
        users: dict[str, User],
        templates: dict[tuple[str, int], dict[str, Any]],
        student_instances: dict[tuple[str, str, int], AnalysisInstance],
    ) -> None:
        style = self.style
        self.stdout.write("")
        self.stdout.write(style.SUCCESS("Example dataset loaded:"))
        self.stdout.write(f"  courses:      {len(courses)}")
        self.stdout.write(
            f"  users:        {len(users)}  (password: {data['users'].get('default_password', 'changeme')})"
        )
        self.stdout.write(f"  analysis types: {AnalysisType.objects.count()}")
        self.stdout.write(f"  instances:    {len(student_instances)} (one per student per announcement)")
        self.stdout.write(f"  assignments:  {StudentAssignment.objects.count()}")
        self.stdout.write(f"  submissions:  {Submission.objects.count()}")
        self.stdout.write("")
        self.stdout.write(style.NOTICE("Announcement windows (relative to now):"))
        for (course_name, number), template in sorted(templates.items()):
            sample = next(
                (i for (su, co, no), i in student_instances.items() if co == course_name and no == number),
                None,
            )
            status = sample.window_status() if sample else "-"
            self.stdout.write(
                f"  {course_name} #{number} {template['type'].name}  [{status:>9}]  "
                f"{template['window_start']:%Y-%m-%d %H:%M} → {template['window_end']:%H:%M}"
            )
        self.stdout.write("")
        self.stdout.write(style.NOTICE("Log in at the API (/api/v1/auth/login) or the built frontend."))
