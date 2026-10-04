"""
Seed a rich demo dataset for staging using the factory-boy factories.

Unlike :cmd:`load_examples` (which reads a fixed set of JSON files), this
command builds the demo environment programmatically from the ``factory.py``
modules that live in each app. That keeps the demo data in code (reviewable,
easy to tweak) and exercises the same factories the test-suite uses.

What it creates, illustrating every feature of the system:

* the ion / substance reference catalog (``create_ion_catalog`` +
  :class:`~substances.factory.SubstanceFactory`),
* four courses (Chemistry / Biology / Pharmacy / Materials), with the
  Chemistry course the active (default) one,
* users — an admin, three assistants (one per course) and twelve students
  (three per course) — **all sharing the password ``FlameCheck32!``** —
  plus student barcodes,
* analysis types (each with a *possible* ion set),
* analysis instances: one per student per announcement, with time windows that
  span the ``open`` / ``too_early`` / ``too_late`` states relative to "now",
* student → instance assignments (the per-student sheet design),
* the singleton :class:`~config.models.GradingConfig` *and* a per-course
  override (to demonstrate per-course grading),
* the singleton :class:`~config.models.AppSettings` (active course),
* a handful of pre-seeded submissions graded through the real
  :meth:`~analyses.models.AnalysisInstance.submit` business logic.

The command is idempotent: re-running it refreshes the demo rows without
duplicating them. Pass ``--reset`` to wipe the seeded domain first (useful
after experimenting).

Run it with::

    uv run python manage.py seed_demo            # create / refresh the demo data
    uv run python manage.py seed_demo --reset    # wipe + re-seed from scratch
"""

from __future__ import annotations

from typing import Any

from config.factory import (
    AssistantCourseFactory,
    CourseFactory,
    GradingConfigFactory,
)
from config.models import AppSettings, AssistantCourse, Course, GradingConfig
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from substances.factory import IonFactory, SubstanceFactory, create_ion_catalog
from substances.models import Ion, Substance
from users.factory import (
    AdminUserFactory,
    AssistantUserFactory,
    StudentBarcodeFactory,
    UserFactory,
)
from users.models import StudentAssignment, StudentBarcode, User

from analyses.factory import AnalysisInstanceFactory, AnalysisTypeFactory
from analyses.factory import _window as _window_for
from analyses.models import AnalysisInstance, AnalysisType, Submission

# Uniform demo password for every account the command creates (see the module
# docstring and the staging docs). Intentionally a fixed, documented value — it
# is the shared password for staging demo accounts, not a secret.
DEMO_PASSWORD: str = "FlameCheck32!"  # noqa: S105

# Course / track layout: (name, semester, track, is_active, is_the_active_course).
# The Chemistry course is the default (active) course the admin sees.
_COURSES: list[tuple[str, str, str, bool, bool]] = [
    ("Inorganic Chemistry WS 2026 - Chemistry", "WS 2026", "chemistry", True, True),
    ("Inorganic Chemistry WS 2026 - Biology", "WS 2026", "biology", True, False),
    ("Inorganic Chemistry WS 2026 - Pharmacy", "WS 2026", "pharmacy", True, False),
    ("Inorganic Chemistry SS 2026 - Materials", "SS 2026", "materials", True, False),
]

# Users: (username, role, first_name, last_name, course_name_or_None).
# Students carry real given/surname pairs; the admin and the assistants use a
# single descriptor kept in ``first_name`` (empty ``last_name``).
_USERS: list[tuple[str, str, str, str, str | None]] = [
    ("admin", "admin", "Demo", "Admin", None),
    ("assistant.chemistry", "assistant", "Chemistry Lab Assistant", "", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("assistant.bio", "assistant", "Biology Lab Assistant", "", "Inorganic Chemistry WS 2026 - Biology"),
    ("assistant.pharmacy", "assistant", "Pharmacy Lab Assistant", "", "Inorganic Chemistry WS 2026 - Pharmacy"),
    ("student-lena", "student", "Lena", "Hoffmann", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("student-max", "student", "Max", "Braun", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("student-petra", "student", "Petra", "Novak", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("student-anna", "student", "Anna", "Schulz", "Inorganic Chemistry WS 2026 - Biology"),
    ("student-ben", "student", "Ben", "Weber", "Inorganic Chemistry WS 2026 - Biology"),
    ("student-clara", "student", "Clara", "Novak", "Inorganic Chemistry WS 2026 - Biology"),
    ("student-david", "student", "David", "Kim", "Inorganic Chemistry WS 2026 - Pharmacy"),
    ("student-emma", "student", "Emma", "Rossi", "Inorganic Chemistry WS 2026 - Pharmacy"),
    ("student-felix", "student", "Felix", "Braun", "Inorganic Chemistry WS 2026 - Pharmacy"),
    ("student-greta", "student", "Greta", "Schmidt", "Inorganic Chemistry SS 2026 - Materials"),
    ("student-hugo", "student", "Hugo", "Fischer", "Inorganic Chemistry SS 2026 - Materials"),
    ("student-ines", "student", "Ines", "Costa", "Inorganic Chemistry SS 2026 - Materials"),
]

# Analysis types: (name, description, possible ion catalog keys).
_TYPES: list[tuple[str, str, list[str]]] = [
    (
        "Cations I & II",
        "Qualitative detection of the main cation groups (groups I and II).",
        ["ammonium", "magnesium", "calcium", "copper", "iron2", "iron3", "aluminium", "zinc", "manganese", "barium"],
    ),
    (
        "Anions & halides",
        "Detection of common anions, including the halides and oxyanions.",
        [
            "chloride",
            "bromide",
            "iodide",
            "sulfate",
            "sulfite",
            "carbonate",
            "phosphate",
            "nitrate",
            "nitrite",
            "sulfide",
        ],
    ),
    (
        "Mixed cation / anion panel",
        "A combined panel covering representative cations and anions.",
        ["sodium", "potassium", "ammonium", "chloride", "sulfate", "carbonate", "nitrate", "phosphate"],
    ),
]

# Announcements: (course_name, number, type_name, window_state, correct ion
# keys, day_offset). window_state drives the time window relative to "now" and
# day_offset shifts it by whole days so a course's analyses span several days
# (crossing a weekend and a week boundary) — see
# :meth:`AnalysisInstanceFactory.make`.
#
# "open" announcements keep day_offset = 0 so their window still straddles
# "now" (the pre-seeded submissions target announcement #1 and need an open
# window to be accepted); the late / early ones are spread across days.
_ANNOUNCEMENTS: list[tuple[str, int, str, str, list[str], int]] = [
    (
        "Inorganic Chemistry WS 2026 - Chemistry",
        1,
        "Cations I & II",
        "open",
        ["ammonium", "calcium", "copper", "barium"],
        0,
    ),
    (
        "Inorganic Chemistry WS 2026 - Chemistry",
        2,
        "Anions & halides",
        "too_late",
        ["chloride", "nitrate", "phosphate"],
        -5,
    ),
    (
        "Inorganic Chemistry WS 2026 - Biology",
        1,
        "Cations I & II",
        "open",
        ["ammonium", "magnesium", "copper", "iron2"],
        0,
    ),
    (
        "Inorganic Chemistry WS 2026 - Biology",
        2,
        "Anions & halides",
        "open",
        ["chloride", "sulfate", "carbonate"],
        0,
    ),
    (
        "Inorganic Chemistry WS 2026 - Biology",
        3,
        "Mixed cation / anion panel",
        "too_late",
        ["sodium", "potassium", "nitrate"],
        -6,
    ),
    (
        "Inorganic Chemistry WS 2026 - Pharmacy",
        1,
        "Cations I & II",
        "open",
        ["calcium", "zinc", "barium", "iron3"],
        0,
    ),
    (
        "Inorganic Chemistry WS 2026 - Pharmacy",
        2,
        "Anions & halides",
        "too_early",
        ["bromide", "sulfite", "phosphate"],
        5,
    ),
    (
        "Inorganic Chemistry SS 2026 - Materials",
        1,
        "Cations I & II",
        "open",
        ["manganese", "aluminium", "iron3"],
        0,
    ),
    (
        "Inorganic Chemistry SS 2026 - Materials",
        2,
        "Mixed cation / anion panel",
        "too_late",
        ["potassium", "carbonate", "phosphate", "nitrate"],
        -4,
    ),
]

# Substances: (name, formula, ion keys). A realistic salt per common ion pair.
_SUBSTANCES: list[tuple[str, str, list[str]]] = [
    ("Ammonium chloride", "NH4Cl", ["ammonium", "chloride"]),
    ("Magnesium sulfate", "MgSO4", ["magnesium", "sulfate"]),
    ("Calcium carbonate", "CaCO3", ["calcium", "carbonate"]),
    ("Copper sulfate", "CuSO4", ["copper", "sulfate"]),
    ("Iron(II) sulfate", "FeSO4", ["iron2", "sulfate"]),
    ("Iron(III) nitrate", "Fe(NO3)3", ["iron3", "nitrate"]),
    ("Aluminium sulfate", "Al2(SO4)3", ["aluminium", "sulfate"]),
    ("Zinc chloride", "ZnCl2", ["zinc", "chloride"]),
    ("Manganese sulfate", "MnSO4", ["manganese", "sulfate"]),
    ("Barium sulfate", "BaSO4", ["barium", "sulfate"]),
    ("Sodium chloride", "NaCl", ["sodium", "chloride"]),
    ("Potassium nitrate", "KNO3", ["potassium", "nitrate"]),
    ("Sodium bromide", "NaBr", ["sodium", "bromide"]),
    ("Potassium iodide", "KI", ["potassium", "iodide"]),
    ("Sodium sulfite", "Na2SO3", ["sodium", "sulfite"]),
    ("Sodium phosphate", "Na3PO4", ["sodium", "phosphate"]),
    ("Sodium nitrate", "NaNO3", ["sodium", "nitrate"]),
    ("Sodium sulfide", "Na2S", ["sodium", "sulfide"]),
]


class Command(BaseCommand):
    """Seed a factory-built demo dataset for staging (users, courses, analyses)."""

    help = (
        "Create a rich demo dataset from the factory.py modules for staging. "
        f"All demo accounts share the password '{DEMO_PASSWORD}'."
    )

    def add_arguments(self, parser: Any) -> None:
        """Register the command-line options (--reset)."""
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Wipe the seeded demo domain (users, courses, analyses) before seeding.",
        )

    # -- entry point ---------------------------------------------------------
    def handle(self, *args: Any, **options: Any) -> None:
        """Seed the demo dataset (optionally after a reset)."""
        self._ensure_schema()  # guard: migrate a fresh (unmigrated) database first
        with transaction.atomic():
            if options["reset"]:
                self._reset()

            self._seed_catalog()
            courses = self._seed_courses()
            users = self._seed_users(courses)
            self._seed_assistant_courses(users, courses)
            types = self._seed_types()
            instances = self._seed_announcements(types, courses, users)
            self._seed_singletons(courses)
            self._seed_submissions(users, instances)
            self._seed_multichoice(courses, users)

            self._print_summary(courses, users, instances)

    # -- schema guard --------------------------------------------------------
    def _ensure_schema(self) -> None:
        """
        Apply migrations first when the database has no schema yet.

        The command targets a fixed set of tables; on a fresh database — e.g.
        right after a migration reset, before ``migrate`` has been run — those
        tables do not exist and the first query fails with ``no such table``.
        When the core table is missing, run ``migrate`` so ``seed_demo --reset``
        is self-contained on a clean DB. On an already-migrated database this
        is a no-op (no migrations are (re)applied as a side effect).
        """
        from django.core.management import call_command
        from django.db import connection

        with connection.cursor() as cursor:
            has_schema = Submission._meta.db_table in connection.introspection.table_names(cursor)
        if not has_schema:
            self.stdout.write(self.style.NOTICE("No schema found - running `migrate` before seeding..."))
            call_command("migrate", interactive=False, verbosity=1)

    # -- reset ---------------------------------------------------------------
    def _reset(self) -> None:
        """Wipe the seeded domain (submissions, assignments, instances, types, demo users/courses, configs)."""
        demo_usernames = [u[0] for u in _USERS]
        demo_course_names = [c[0] for c in _COURSES]

        Submission.objects.all().delete()
        StudentAssignment.objects.all().delete()
        AnalysisInstance.objects.all().delete()
        AnalysisType.objects.all().delete()
        AssistantCourse.objects.all().delete()
        # Multiple-choice domain (cleared alongside the analyses domain).
        from multichoice.models import MCCard, MCOption, MCQuestion, MCSheet, MCStudentAssignment, MCSubmission

        MCSubmission.objects.all().delete()
        MCStudentAssignment.objects.all().delete()
        MCSheet.objects.all().delete()
        MCCard.objects.all().delete()
        MCOption.objects.all().delete()
        MCQuestion.objects.all().delete()
        GradingConfig.objects.all().delete()
        AppSettings.objects.all().delete()
        # Demo students are the ones that carry a barcode; drop those and the
        # named demo users (covers leftovers from earlier seeding runs too).
        barcode_students = list(StudentBarcode.objects.values_list("student_id", flat=True))
        StudentBarcode.objects.all().delete()
        User.objects.filter(id__in=barcode_students).delete()
        User.objects.filter(username__in=demo_usernames).delete()
        Course.objects.filter(name__in=demo_course_names).delete()
        self.stdout.write(self.style.WARNING("Reset: cleared demo users, courses and the analyses domain."))

    # -- reference catalog ---------------------------------------------------
    def _seed_catalog(self) -> None:
        """Create (idempotently) the ion catalog and the demo substances."""
        create_ion_catalog()  # the full ION_CATALOG
        ion_by_key = {i.name: i for i in Ion.objects.all()}
        for name, formula, keys in _SUBSTANCES:
            ions = [ion_by_key[k] for k in keys if k in ion_by_key]
            SubstanceFactory(name=name, formula=formula, ions=ions)
        self.stdout.write(f"  catalog: {Ion.objects.count()} ions, {Substance.objects.count()} substances")

    # -- courses -------------------------------------------------------------
    def _seed_courses(self) -> dict[str, Course]:
        """Create the demo courses; returns a name → course map."""
        result: dict[str, Course] = {}
        for name, semester, track, is_active, _ in _COURSES:
            course = CourseFactory(name=name, semester=semester, track=track, is_active=is_active)
            result[name] = course
        return result

    # -- users ---------------------------------------------------------------
    def _seed_users(self, courses: dict[str, Course]) -> dict[str, User]:
        """
        Create the demo users (uniform password) + student barcodes.

        ``UserFactory`` overrides ``_create`` (to hash the password via
        ``create_user``/``create_superuser``), which bypasses its
        ``django_get_or_create``; so existence is handled explicitly here to
        keep the command idempotent.
        """
        result: dict[str, User] = {}
        for username, role, first_name, last_name, course_name in _USERS:
            course = courses.get(course_name) if course_name else None
            email = f"{username}@flamecheck.local"
            existing = User.objects.filter(username=username).first()
            if existing is None:
                if role == "admin":
                    user = AdminUserFactory(username=username, email=email)
                elif role == "assistant":
                    user = AssistantUserFactory(username=username, email=email)
                else:
                    user = UserFactory(username=username, email=email)
            else:
                user = existing
            # Sync profile fields, role flags and the uniform demo password
            # (idempotent).
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.course = course
            user.role = User.Role(role)
            user.is_staff = role == "admin"
            user.is_superuser = role == "admin"
            user.set_password(DEMO_PASSWORD)
            user.save()
            if user.is_student and not StudentBarcode.objects.filter(student=user).exists():
                StudentBarcodeFactory(student=user)
            result[username] = user
        return result

    # -- assistant → course links -------------------------------------------
    def _seed_assistant_courses(self, users: dict[str, User], courses: dict[str, Course]) -> None:
        """Link each assistant to the course they are named after."""
        for username, role, _first, _last, course_name in _USERS:
            if role != "assistant" or not course_name:
                continue
            assistant = users.get(username)
            course = courses.get(course_name)
            if assistant is None or course is None:
                continue
            AssistantCourseFactory(assistant=assistant, course=course)

    # -- analysis types ------------------------------------------------------
    def _seed_types(self) -> dict[str, AnalysisType]:
        """Create the demo analysis types with their possible ion sets."""
        result: dict[str, AnalysisType] = {}
        ion_by_symbol = {i.symbol: i for i in Ion.objects.all()}
        for name, description, keys in _TYPES:
            ions = [ion_by_symbol[self._symbol_for_key(k)] for k in keys]
            # The factory returns an AnalysisType; the ignore silences mypy,
            # which cannot see the factory's return type (no py.typed stubs).
            analysis_type: AnalysisType = AnalysisTypeFactory(  # type: ignore[assignment]
                name=name, description=description, possible_ions=ions
            )
            result[name] = analysis_type
        return result

    @staticmethod
    def _symbol_for_key(key: str) -> str:
        """Map an :data:`ION_CATALOG` key (e.g. ``'iron2'``) to its ion symbol."""
        from substances.factory import ION_CATALOG

        return ION_CATALOG[key][0]

    # -- announcements (instances + assignments) -----------------------------
    def _seed_announcements(
        self,
        types: dict[str, AnalysisType],
        courses: dict[str, Course],
        users: dict[str, User],
    ) -> dict[tuple[str, int], list[AnalysisInstance]]:
        """
        For each announcement, give every enrolled student their own instance.

        Returns a (course name, number) → [instance per student] map so the
        submission step can target specific (student, instance) pairs.
        """
        result: dict[tuple[str, int], list[AnalysisInstance]] = {}
        ion_by_key: dict[str, Ion] = {}
        for _course_name, _number, _type_name, _state, keys, _offset in _ANNOUNCEMENTS:
            for k in keys:
                ion_by_key.setdefault(k, IonFactory.make(k))

        for course_name, number, type_name, state, keys, day_offset in _ANNOUNCEMENTS:
            course = courses.get(course_name)
            analysis_type = types.get(type_name)
            if course is None or analysis_type is None:
                raise CommandError(f"Unknown course/type for announcement: {course_name!r} #{number} {type_name!r}")
            correct_ions = [ion_by_key[k] for k in keys]

            students = [u for u in users.values() if u.is_student and u.course_id == course.id]
            created: list[AnalysisInstance] = []
            for student in students:
                # Reuse an existing (student, course, number) assignment if present
                # (idempotency); otherwise create a dedicated instance.
                existing = StudentAssignment.objects.filter(student=student, course=course, number=number).first()
                if existing is not None:
                    instance = existing.instance
                    # Keep the demo window current (re-seed relative to now) so
                    # the open / early / late states stay meaningful.
                    instance.window_start, instance.window_end = _window_for(state, day_offset)
                    instance.save(update_fields=["window_start", "window_end"])
                else:
                    instance = AnalysisInstanceFactory.make(
                        window=state,
                        day_offset=day_offset,
                        type=analysis_type,
                        course=course,
                        number=number,
                        correct_ions=correct_ions,
                    )
                    StudentAssignment.objects.create(student=student, instance=instance, course=course, number=number)
                instance.correct_ions.set([i.id for i in correct_ions])
                created.append(instance)
            result[(course_name, number)] = created
        return result

    # -- singletons (grading + app settings) ---------------------------------
    def _seed_singletons(self, courses: dict[str, Course]) -> None:
        """Create the global grading config, a per-course override, app settings."""
        GradingConfigFactory()  # the global default (pk=1, course=None)

        # A per-course override on the Biology course to demonstrate per-course
        # grading (stricter: all-or-nothing points per completed analysis, one
        # attempt, higher pass line). The factory pins pk=1 (the singleton), so
        # a per-course row is written via the model.
        biology = courses.get("Inorganic Chemistry WS 2026 - Biology")
        if biology is not None:
            GradingConfig.objects.update_or_create(
                course=biology,
                defaults={
                    "grading_mode": "per_analysis",
                    "points_per_correct_ion": 20,
                    "max_submissions_per_analysis": 1,
                    "final_score_strategy": "last",
                    "passing_score": 40,
                },
            )

        active_course = None
        for name, _sem, _track, _active, is_the_active in _COURSES:
            if is_the_active:
                active_course = courses.get(name)
        settings_row = AppSettings.get_instance()
        settings_row.points_per_analysis = 20
        settings_row.analyses_per_course = 3
        settings_row.active_course = active_course
        settings_row.save()

    # -- pre-seeded submissions ----------------------------------------------
    def _seed_submissions(
        self, users: dict[str, User], instances: dict[tuple[str, int], list[AnalysisInstance]]
    ) -> None:
        """Grade a handful of submissions through the real submit() logic."""
        # (student username, course name, number, how the answer relates to the key)
        # 'correct' -> selects exactly the answer key; 'partial' -> selects a
        # subset (misses some); 'wrong' -> selects an ion outside the key.
        plans: list[tuple[str, str, int, str]] = [
            ("student-lena", "Inorganic Chemistry WS 2026 - Chemistry", 1, "correct"),
            ("student-max", "Inorganic Chemistry WS 2026 - Chemistry", 1, "partial"),
            ("student-anna", "Inorganic Chemistry WS 2026 - Biology", 1, "correct"),
            ("student-ben", "Inorganic Chemistry WS 2026 - Biology", 1, "partial"),
            ("student-david", "Inorganic Chemistry WS 2026 - Pharmacy", 1, "correct"),
            ("student-greta", "Inorganic Chemistry SS 2026 - Materials", 1, "partial"),
        ]
        for student_username, course_name, number, kind in plans:
            student = users.get(student_username)
            instances_for = instances.get((course_name, number), [])
            instance = next(
                (i for i in instances_for if i.assignments.filter(student=student).exists()),
                None,
            )
            if student is None or instance is None:
                self.stdout.write(
                    self.style.WARNING(f"  skip submission: no instance for {student_username} #{number}")
                )
                continue
            selected = self._selection_for(instance, kind)
            # A stable idempotency key per (student, announcement) makes the
            # command idempotent: re-running returns the original submission.
            key = f"seed-demo-{student_username}-{number}"
            try:
                submission = instance.submit(student, selected, idempotency_key=key)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  skip submission {student_username} #{number}: {exc}"))
                continue
            self.stdout.write(
                f"  submission: {student_username} #{number}  score={submission.score}/"
                f"{submission.ideal_score}  ({kind})"
            )

    @staticmethod
    def _selection_for(instance: AnalysisInstance, kind: str) -> list[int]:
        """Pick the ion ids a demo student would select for a given ``kind``."""
        correct_ids = list(instance.correct_ions.values_list("id", flat=True))
        possible_ids = list(instance.type.possible_ions.values_list("id", flat=True))
        if not correct_ids:
            return []
        match kind:
            case "correct":
                return correct_ids
            case "partial":
                # Select the first half of the answer key (miss the rest).
                return correct_ids[: max(1, len(correct_ids) // 2)]
            case "wrong":
                # Select an ion that is possible but not in the key, plus one correct.
                wrong = next((i for i in possible_ids if i not in set(correct_ids)), None)
                return [correct_ids[0]] if wrong is None else [wrong, correct_ids[0]]
            case _:
                return correct_ids

    # -- multiple choice -----------------------------------------------------
    def _seed_multichoice(self, courses: dict[str, Course], users: dict[str, User]) -> None:
        """
        Seed a small, self-consistent multiple-choice set for the demo.

        For the first (Chemistry) course: three flame-test questions grouped
        into one card, one open sheet assigned to every chemistry student, and
        two example submissions (one fully correct, one with a wrong answer).
        """
        from datetime import timedelta

        from django.utils import timezone
        from multichoice.models import (
            MCCard,
            MCCardQuestion,
            MCOption,
            MCQuestion,
            MCSheet,
            MCStudentAssignment,
            MCSubmission,
        )

        course_name = _COURSES[0][0]
        course = courses.get(course_name)
        if course is None:
            return
        students = [u for u in users.values() if u.is_student and u.course_id == course.id]
        if not students:
            return

        def make_question(text: str, options: list[tuple[str, bool]]) -> MCQuestion:
            q = MCQuestion.objects.create(
                course=course,
                text=text,
                description="Flame-test knowledge check (demo).",
                remarks="Demo content for the multiple-choice feature.",
            )
            for i, (opt_text, correct) in enumerate(options):
                MCOption.objects.create(question=q, text=opt_text, is_correct=correct, sort_order=i)
            return q

        questions = [
            make_question(
                "Which flame colour does sodium (Na+1) produce?",
                [("Yellow", True), ("Violet", False), ("Green", False), ("Brick red", False)],
            ),
            make_question(
                "Which flame colour does copper (Cu+2) produce?",
                [("Green", True), ("Yellow", False), ("Crimson", False), ("No colour", False)],
            ),
            make_question(
                "Which flame colour does potassium (K+1) produce?",
                [("Lilac (violet)", True), ("Yellow", False), ("Green", False), ("Orange", False)],
            ),
        ]
        card = MCCard.objects.create(
            course=course,
            title="Flame test card",
            description="Three flame-test questions (demo).",
            remarks="Demo card for the multiple-choice feature.",
        )
        for i, q in enumerate(questions):
            MCCardQuestion.objects.create(card=card, question=q, order=i)

        now = timezone.now().replace(microsecond=0)
        sheet = MCSheet.objects.create(
            card=card,
            course=course,
            window_start=now - timedelta(hours=1),
            window_end=now + timedelta(hours=23),
            number=1,
        )
        for student in students:
            MCStudentAssignment.objects.create(course=course, student=student, sheet=sheet, number=1)

        def submit(username: str, wrong_first: bool) -> None:
            student = users.get(username)
            if student is None:
                return
            answers: dict[int, int] = {}
            for q in questions:
                correct = q.correct_option()
                if wrong_first and q is questions[0]:
                    answers[q.id] = q.options_set.filter(is_correct=False).first().id
                else:
                    answers[q.id] = correct.id
            MCSubmission.objects.create(
                sheet=sheet,
                student=student,
                submission_number=1,
                idempotency_key=f"seed-mc-{student.id}",
                answers=answers,
                score=8 if wrong_first else 10,
                correct_count=2 if wrong_first else 3,
                wrong_count=1 if wrong_first else 0,
                ideal_score=10,
            )

        submit("student-lena", wrong_first=False)
        submit("student-max", wrong_first=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"  multichoice:    1 card, {len(questions)} questions, sheet for {len(students)} students"
            )
        )

    # -- summary -------------------------------------------------------------
    def _print_summary(
        self,
        courses: dict[str, Course],
        users: dict[str, User],
        instances: dict[tuple[str, int], list[AnalysisInstance]],
    ) -> None:
        style = self.style
        n_instances = sum(len(v) for v in instances.values())
        self.stdout.write("")
        self.stdout.write(style.SUCCESS("Demo dataset seeded (staging):"))
        self.stdout.write(f"  courses:        {len(courses)}")
        self.stdout.write(f"  users:          {len(users)}  (password: {DEMO_PASSWORD})")
        self.stdout.write(
            f"    admin:      {sum(1 for u in users.values() if u.is_admin)}   "
            f"assistant:    {sum(1 for u in users.values() if u.is_assistant)}   "
            f"student:      {sum(1 for u in users.values() if u.is_student)}"
        )
        self.stdout.write(f"  analysis types: {AnalysisType.objects.count()}")
        self.stdout.write(f"  instances:      {n_instances}  (one per student per announcement)")
        self.stdout.write(f"  assignments:    {StudentAssignment.objects.count()}")
        self.stdout.write(f"  barcodes:       {StudentBarcode.objects.count()}")
        self.stdout.write(f"  submissions:    {Submission.objects.count()}")
        self.stdout.write(f"  grading configs:{len(list(GradingConfig.objects.all()))} (global + per-course)")
        self.stdout.write("")
        self.stdout.write(style.NOTICE("Announcement windows (relative to now):"))
        for (course_name, number), group in sorted(instances.items()):
            sample = group[0] if group else None
            status = sample.window_status() if sample else "-"
            self.stdout.write(f"  {course_name} #{number}  [{status:>9}]  ({len(group)} students)")
        self.stdout.write("")
        self.stdout.write(style.NOTICE(f"Log in with any demo account and the password '{DEMO_PASSWORD}'."))
