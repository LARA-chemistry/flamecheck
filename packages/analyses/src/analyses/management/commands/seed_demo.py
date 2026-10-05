"""
Seed a rich, realistic demo dataset for staging using the factory-boy factories.

Unlike :cmd:`load_examples` (which reads a fixed set of JSON files), this command
builds the demo environment programmatically from the ``factory.py`` modules that
live in each app. That keeps the demo data in code (reviewable, easy to tweak) and
exercises the same factories the test-suite uses.

What it creates, illustrating every feature of the system across five courses:

* **Geology** (the active / default course) - the "realistic" showcase: the salts
  from ``examples/substance_list.csv`` are imported as substances, and each student
  gets the full task programme (Practice, Analysis 1-5) whose *correct ion set* is
  the union of the ions of a few of those salts. Graded per analysis with a retry
  penalty (10 -> 8 -> 6). Plus the European-Pharmacopoeia monograph multiple-choice
  card (identity / purity / monograph, graded all-or-nothing).
* **Chemistry** - the "new analysis" (repeat) submission workflow: a wrong
  submission hands the student a fresh re-trial analysis of the same type.
* **Medicine** - a simple per-analysis course (three analyses, three trials) plus a
  basic chemistry multiple-choice card.
* **Biology** - the per-ion workflow with no retries, plus a basic multiple-choice
  card.
* **Materials** - a straightforward per-ion course on the global grading config.

Every demo student carries an integer ``labspace_id`` (1, 2, 3 per course) and each
analysis instance is labelled ``<type name, no spaces>_<labspace_id>`` (e.g.
``Cations1_1``), so sheets are identifiable per student.

Users - an admin, five assistants (one per course) and fifteen students (three per
course) - **all share the password** ``FlameCheck32!`` - plus student barcodes.

The command is idempotent: re-running it refreshes the demo rows without
duplicating them. Pass ``--reset`` to wipe the seeded domain first (useful after
experimenting).

Run it with::

    uv run python manage.py seed_demo            # create / refresh the demo data
    uv run python manage.py seed_demo --reset    # wipe + re-seed from scratch
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
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
# docstring and the staging docs). Intentionally a fixed, documented value - it
# is the shared password for staging demo accounts, not a secret.
DEMO_PASSWORD: str = "FlameCheck32!"  # noqa: S105

# Course / track layout: (name, semester, track, is_active, is_the_active_course).
# Geology is the active (default) course - the realistic showcase.
_COURSES: list[tuple[str, str, str, bool, bool]] = [
    ("Inorganic Chemistry WS 2026 - Chemistry", "WS 2026", "chemistry", True, False),
    ("Inorganic Chemistry WS 2026 - Biology", "WS 2026", "biology", True, False),
    ("Inorganic Chemistry WS 2026 - Geology", "WS 2026", "geology", True, True),
    ("Inorganic Chemistry WS 2026 - Medicine", "WS 2026", "medicine", True, False),
    ("Inorganic Chemistry SS 2026 - Materials", "SS 2026", "materials", True, False),
]

# Users: (username, role, first_name, last_name, course_name_or_None).
# Students carry real given/surname pairs; the admin and the assistants use a
# single descriptor kept in ``first_name`` (empty ``last_name``).
_USERS: list[tuple[str, str, str, str, str | None]] = [
    ("admin", "admin", "Demo", "Admin", None),
    ("assistant.chemistry", "assistant", "Chemistry Lab Assistant", "", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("assistant.bio", "assistant", "Biology Lab Assistant", "", "Inorganic Chemistry WS 2026 - Biology"),
    ("assistant.geology", "assistant", "Geology Lab Assistant", "", "Inorganic Chemistry WS 2026 - Geology"),
    ("assistant.medicine", "assistant", "Medicine Lab Assistant", "", "Inorganic Chemistry WS 2026 - Medicine"),
    ("assistant.materials", "assistant", "Materials Lab Assistant", "", "Inorganic Chemistry SS 2026 - Materials"),
    ("student-lena", "student", "Lena", "Hoffmann", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("student-max", "student", "Max", "Braun", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("student-petra", "student", "Petra", "Novak", "Inorganic Chemistry WS 2026 - Chemistry"),
    ("student-anna", "student", "Anna", "Schulz", "Inorganic Chemistry WS 2026 - Biology"),
    ("student-ben", "student", "Ben", "Weber", "Inorganic Chemistry WS 2026 - Biology"),
    ("student-clara", "student", "Clara", "Nowak", "Inorganic Chemistry WS 2026 - Biology"),
    ("student-david", "student", "David", "Kim", "Inorganic Chemistry WS 2026 - Geology"),
    ("student-emma", "student", "Emma", "Rossi", "Inorganic Chemistry WS 2026 - Geology"),
    ("student-felix", "student", "Felix", "Braun", "Inorganic Chemistry WS 2026 - Geology"),
    ("student-mia", "student", "Mia", "Farah", "Inorganic Chemistry WS 2026 - Medicine"),
    ("student-omar", "student", "Omar", "Haddad", "Inorganic Chemistry WS 2026 - Medicine"),
    ("student-lily", "student", "Lily", "Chen", "Inorganic Chemistry WS 2026 - Medicine"),
    ("student-greta", "student", "Greta", "Schmidt", "Inorganic Chemistry SS 2026 - Materials"),
    ("student-hugo", "student", "Hugo", "Fischer", "Inorganic Chemistry SS 2026 - Materials"),
    ("student-ines", "student", "Ines", "Costa", "Inorganic Chemistry SS 2026 - Materials"),
]

# Shared analysis types (used by Chemistry, Biology and Materials):
# (name, description, possible ion catalog keys).
_SHARED_TYPES: list[tuple[str, str, list[str]]] = [
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

# Simple medicine-track analysis types: (name, description, possible ion keys).
_MEDICINE_TYPES: list[tuple[str, str, list[str]]] = [
    ("Medicine Analysis 1", "Basic qualitative analysis (medicine track).", ["sodium", "chloride", "sulfate"]),
    (
        "Medicine Analysis 2",
        "Intermediate qualitative analysis (medicine track).",
        ["potassium", "ammonium", "nitrate", "carbonate"],
    ),
    (
        "Medicine Analysis 3",
        "Advanced qualitative analysis (medicine track).",
        ["calcium", "magnesium", "chloride", "nitrate", "phosphate"],
    ),
]

# Full cation / anion scope for the Geology programme (catalog keys).
_GEO_CATIONS = [
    "sodium",
    "potassium",
    "ammonium",
    "lithium",
    "barium",
    "magnesium",
    "calcium",
    "aluminium",
    "zinc",
    "iron2",
    "iron3",
    "manganese",
    "manganese4",
    "manganese6",
    "manganese7",
    "nickel",
    "cobalt2",
    "cobalt3",
    "copper",
    "silver",
    "lead",
    "tin",
]
_GEO_ANIONS = [
    "chloride",
    "sulfate",
    "nitrate",
    "carbonate",
    "acetate",
    "thiocyanate",
    "sulfide",
    "bromide",
    "iodide",
    "phosphate",
    "nitrite",
]

# Geology analysis types: (name, description, salt_count, cation keys, anion keys, mode).
# mode is "full" (cations + anions), "cations" (cation scope only) or "anions"
# (anion scope only). The salt count is the number of salts mixed into each
# student's sample for that analysis.
_GEOLOGY_TYPES: list[tuple[str, str, int, list[str], list[str], str]] = [
    (
        "Practice Analysis",
        "Practice: identify the ions of a single salt.",
        1,
        ["sodium", "potassium", "ammonium"],
        ["chloride", "sulfate", "nitrate"],
        "full",
    ),
    (
        "Analysis 1",
        "Two salts. Cations: Na, K, NH4. Anions: Cl, SO4, NO3.",
        2,
        ["sodium", "potassium", "ammonium"],
        ["chloride", "sulfate", "nitrate"],
        "full",
    ),
    (
        "Analysis 2",
        "Up to three salts. Cations: Na, K, NH4, Li, Ba, Mg, Ca. Anions: Cl, SO4, NO3, CO3.",
        3,
        ["sodium", "potassium", "ammonium", "lithium", "barium", "magnesium", "calcium"],
        ["chloride", "sulfate", "nitrate", "carbonate"],
        "full",
    ),
    (
        "Analysis 3",
        "Up to three salts. Cations only, over the full cation scope.",
        3,
        _GEO_CATIONS,
        [],
        "cations",
    ),
    (
        "Analysis 4",
        "Up to four salts. Anions only, over the full anion scope.",
        4,
        [],
        _GEO_ANIONS,
        "anions",
    ),
    (
        "Analysis 5",
        "Up to four salts. Full analysis over the entire scope treated so far.",
        4,
        _GEO_CATIONS,
        _GEO_ANIONS,
        "full",
    ),
]

# Announcements for the non-Geology courses:
# (course_name, number, type_name, window_state, correct ion keys, day_offset).
# "open" announcements keep day_offset = 0 so their window straddles "now" (the
# pre-seeded submissions target announcement #1 and need an open window); the
# late ones are shifted back across a week boundary.
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
        "Inorganic Chemistry WS 2026 - Medicine",
        1,
        "Medicine Analysis 1",
        "open",
        ["sodium", "chloride"],
        0,
    ),
    (
        "Inorganic Chemistry WS 2026 - Medicine",
        2,
        "Medicine Analysis 2",
        "open",
        ["potassium", "nitrate"],
        0,
    ),
    (
        "Inorganic Chemistry WS 2026 - Medicine",
        3,
        "Medicine Analysis 3",
        "too_early",
        ["calcium", "phosphate"],
        0,
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

# Base substances (name, formula, ion keys): one realistic salt per common ion
# pair, used as reference material for the shared / medicine / materials types.
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
    """Seed a factory-built, realistic demo dataset (users, courses, analyses)."""

    help = (
        "Create a rich demo dataset from the factory.py modules for staging. "
        f"All demo accounts share the password '{DEMO_PASSWORD}'."
    )

    # The CSV ion strings that need remapping onto a single canonical ion (the
    # CSV folds multi-valence metals, e.g. "Fe+2/3", into one token).
    _CSV_ION_MAP: dict[str, str] = {"Fe+2/3": "Fe+2", "Sn+2/4": "Sn+2"}

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
            self._seed_geology(courses, users, types)
            self._seed_singletons(courses)
            self._seed_submissions(users, instances)
            self._seed_multichoice(courses, users)
            self._seed_geology_monograph(courses, users)

            self._print_summary(courses, users, instances)

    # -- schema guard --------------------------------------------------------
    def _ensure_schema(self) -> None:
        """
        Apply migrations first when the database has no schema yet.

        The command targets a fixed set of tables; on a fresh database - e.g.
        right after a migration reset, before ``migrate`` has been run - those
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
        """Create (idempotently) the ion catalog and the base demo substances."""
        create_ion_catalog()  # the full ION_CATALOG (incl. the extended set)
        for name, formula, keys in _SUBSTANCES:
            ions = [IonFactory.make(k) for k in keys]
            SubstanceFactory(name=name, formula=formula, ions=ions)
        self.stdout.write(f"  catalog: {Ion.objects.count()} ions, {Substance.objects.count()} base substances")

    # -- courses -------------------------------------------------------------
    def _seed_courses(self) -> dict[str, Course]:
        """Create the demo courses; returns a name -> course map."""
        result: dict[str, Course] = {}
        for name, semester, track, is_active, _ in _COURSES:
            course: Course = CourseFactory(name=name, semester=semester, track=track, is_active=is_active)
            result[name] = course
        return result

    # -- users ---------------------------------------------------------------
    def _seed_users(self, courses: dict[str, Course]) -> dict[str, User]:
        """
        Create the demo users (uniform password) + student barcodes.

        Students are assigned an integer ``labspace_id`` (1, 2, 3, ...) in the
        order they appear within their course. ``UserFactory`` overrides
        ``_create`` (to hash the password via ``create_user``/
        ``create_superuser``), which bypasses its ``django_get_or_create``; so
        existence is handled explicitly here to keep the command idempotent.
        """
        result: dict[str, User] = {}
        labspace_counter: dict[str, int] = {}
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
            if user.is_student and course is not None:
                # Integer labspace ids, 1..N per course, stable across runs.
                labspace_counter[course.name] = labspace_counter.get(course.name, 0) + 1
                user.labspace_id = str(labspace_counter[course.name])
            user.save()
            if user.is_student and not StudentBarcode.objects.filter(student=user).exists():
                StudentBarcodeFactory(student=user)
            result[username] = user
        return result

    # -- assistant -> course links -------------------------------------------
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
        """Create the shared, medicine and Geology analysis types."""
        result: dict[str, AnalysisType] = {}

        def make(name: str, description: str, keys: list[str], max_repetitions: int = 2) -> AnalysisType:
            ions = [IonFactory.make(k) for k in keys]
            analysis_type: AnalysisType = AnalysisTypeFactory(  # type: ignore[assignment]
                name=name, description=description, possible_ions=ions, max_repetitions=max_repetitions
            )
            result[name] = analysis_type
            return analysis_type

        for name, description, keys in _SHARED_TYPES:
            make(name, description, keys)
        for name, description, keys in _MEDICINE_TYPES:
            make(name, description, keys, max_repetitions=0)
        for name, description, _count, cation_keys, anion_keys, _mode in _GEOLOGY_TYPES:
            make(name, description, list(cation_keys) + list(anion_keys), max_repetitions=0)
        return result

    # -- announcements (instances + assignments) -----------------------------
    def _seed_announcements(
        self,
        types: dict[str, AnalysisType],
        courses: dict[str, Course],
        users: dict[str, User],
    ) -> dict[tuple[str, int], list[AnalysisInstance]]:
        """
        For each non-Geology announcement, give every enrolled student an instance.

        Returns a (course name, number) -> [instance per student] map so the
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
                existing = StudentAssignment.objects.filter(student=student, course=course, number=number).first()
                if existing is not None:
                    instance = existing.instance
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
                instance.label = self._instance_label(analysis_type.name, student.labspace_id)
                instance.correct_ions.set([i.id for i in correct_ions])
                instance.save(update_fields=["label"])
                created.append(instance)
            result[(course_name, number)] = created
        return result

    @staticmethod
    def _instance_label(type_name: str, labspace_id: str) -> str:
        """Build the per-student label, e.g. ``'Cations 1'`` + ``'1'`` -> ``'Cations1_1'``."""
        return f"{type_name.replace(' ', '')}_{labspace_id or '0'}"

    # -- Geology showcase (CSV salts + task programme) ------------------------
    def _load_csv_salts(self, ion_by_symbol: dict[str, Ion]) -> list[dict[str, Any]]:
        """
        Import the salts from ``examples/substance_list.csv`` as Substance rows.

        Returns a list of dicts with ``substance``, ``ions``, ``cations`` and
        ``anions`` (canonical :class:`Ion` objects).
        """
        path = Path(__file__).resolve().parents[6] / "examples" / "substance_list.csv"
        if not path.exists():
            raise CommandError(f"Substance list not found at {path}; cannot seed the Geology course.")
        lines = path.read_text(encoding="utf-8").splitlines()
        start = next((i for i, line in enumerate(lines) if line.startswith("name;")), None)
        if start is None:
            raise CommandError(f"No header row found in {path}.")
        reader = csv.DictReader(io.StringIO("\n".join(lines[start:])), delimiter=";")
        salts: list[dict[str, Any]] = []
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            ion_symbols = [s.strip() for s in (row.get("ions") or "").split(",") if s.strip()]
            ions: list[Ion] = []
            for symbol in ion_symbols:
                canonical = self._CSV_ION_MAP.get(symbol, symbol)
                ion = ion_by_symbol.get(canonical)
                if ion is not None:
                    ions.append(ion)
            substance = SubstanceFactory(
                name=name,
                formula=(row.get("formula") or "").strip(),
                ions=ions,
                pubchem_id=(row.get("pubchem_id") or "").strip(),
                wikipedia_link=(row.get("wikipedia_link") or "").strip(),
            )
            cations = [i for i in ions if i.kind == Ion.Kind.CATION]
            anions = [i for i in ions if i.kind == Ion.Kind.ANION]
            salts.append({"substance": substance, "ions": ions, "cations": cations, "anions": anions})
        return salts

    def _pick_salts(
        self,
        compatible: list[dict[str, Any]],
        n: int,
        offset: int,
        distinct_key: Callable[[dict[str, Any]], str],
    ) -> list[dict[str, Any]]:
        """Pick up to ``n`` salts with distinct ``distinct_key`` (rotated by ``offset``)."""
        if not compatible:
            return []
        pool = compatible[offset % len(compatible) :] + compatible[: offset % len(compatible)]
        picked: list[dict[str, Any]] = []
        seen: set[str] = set()
        for salt in pool:
            key = str(distinct_key(salt))
            if key in seen:
                continue
            picked.append(salt)
            seen.add(key)
            if len(picked) == n:
                break
        return picked

    def _seed_geology(self, courses: dict[str, Course], users: dict[str, User], types: dict[str, AnalysisType]) -> None:
        """
        Seed the Geology showcase with the CSV salts and the full task programme.

        Each student gets every analysis type; the correct ion set is the union of
        the ions of that student's salts, restricted to the type's scope.
        """
        course = courses.get("Inorganic Chemistry WS 2026 - Geology")
        if course is None:
            return
        students = sorted(
            (u for u in users.values() if u.is_student and u.course_id == course.id),
            key=lambda u: int(u.labspace_id or 0),
        )
        if not students:
            return

        ion_by_symbol = {i.symbol: i for i in Ion.objects.all()}
        salts = self._load_csv_salts(ion_by_symbol)

        for number, (name, _description, salt_count, cation_keys, anion_keys, mode) in enumerate(
            _GEOLOGY_TYPES, start=1
        ):
            analysis_type = types.get(name)
            if analysis_type is None:
                continue
            possible = set(analysis_type.possible_ions.values_list("id", flat=True))
            cation_set = {IonFactory.make(k).id for k in cation_keys}
            anion_set = {IonFactory.make(k).id for k in anion_keys}
            # Compatible salts: for "full" both ions must be in scope; for the
            # single-scope analyses only the relevant ion must be in scope.
            if mode == "full":
                compatible = [
                    s
                    for s in salts
                    if s["cations"] and s["anions"] and s["cations"][0].id in possible and s["anions"][0].id in possible
                ]
            elif mode == "cations":
                compatible = [s for s in salts if s["cations"] and s["cations"][0].id in cation_set]
            else:  # anions
                compatible = [s for s in salts if s["anions"] and s["anions"][0].id in anion_set]

            for idx, student in enumerate(students):
                picked = self._pick_salts(
                    compatible,
                    salt_count,
                    offset=idx,
                    distinct_key=lambda s, _mode=mode: (
                        s["cations"][0].symbol
                        if _mode == "cations"
                        else s["anions"][0].symbol
                        if _mode == "anions"
                        else s["substance"].name
                    ),
                )
                correct_ions: list[Ion] = []
                for s in picked:
                    for ion in s["ions"]:
                        if ion.id in possible and ion not in correct_ions:
                            correct_ions.append(ion)
                label = self._instance_label(analysis_type.name, student.labspace_id)
                existing = StudentAssignment.objects.filter(
                    student=student, course=course, instance__type=analysis_type
                ).first()
                if existing is not None:
                    instance = existing.instance
                else:
                    instance = AnalysisInstanceFactory.make(
                        window="open",
                        type=analysis_type,
                        course=course,
                        number=number,
                    )
                    StudentAssignment.objects.create(student=student, instance=instance, course=course, number=number)
                instance.correct_ions.set([i.id for i in correct_ions])
                instance.label = label
                instance.assigned_substances.set([s["substance"].id for s in picked])
                instance.save(update_fields=["label"])
        self.stdout.write(
            self.style.SUCCESS(
                f"  geology:       {len(salts)} CSV salts, {len(_GEOLOGY_TYPES)} analyses x {len(students)} students"
            )
        )

    # -- singletons (grading + app settings) ---------------------------------
    def _seed_singletons(self, courses: dict[str, Course]) -> None:
        """Create the global grading config, per-course overrides, app settings."""
        GradingConfigFactory()  # the global default (pk=1, course=None)

        geology = courses.get("Inorganic Chemistry WS 2026 - Geology")
        if geology is not None:
            # Per-analysis, all-or-nothing, with a -2 / -4 retry penalty (10/8/6).
            GradingConfig.objects.update_or_create(
                course=geology,
                defaults={
                    "grading_mode": "per_analysis",
                    "points_per_correct_ion": 10,
                    "penalty_second_submission": 2,
                    "penalty_third_submission": 4,
                    "max_submissions_per_analysis": 3,
                    "final_score_strategy": "last",
                    "passing_score": 30,
                    "mc_points_per_card": 10,
                    "mc_penalty_per_wrong": 10,
                },
            )

        chemistry = courses.get("Inorganic Chemistry WS 2026 - Chemistry")
        if chemistry is not None:
            # "New analysis" (repeat) workflow: a wrong submission yields a fresh
            # re-trial analysis of the same type; each superseded attempt costs 5.
            GradingConfig.objects.update_or_create(
                course=chemistry,
                defaults={
                    "grading_mode": "per_analysis",
                    "points_per_correct_ion": 10,
                    "submission_mode": "new_analysis",
                    "max_submissions_per_analysis": 1,
                    "retry_point_deduction": 5,
                    "final_score_strategy": "last",
                    "passing_score": 30,
                },
            )

        medicine = courses.get("Inorganic Chemistry WS 2026 - Medicine")
        if medicine is not None:
            GradingConfig.objects.update_or_create(
                course=medicine,
                defaults={
                    "grading_mode": "per_analysis",
                    "points_per_correct_ion": 10,
                    "penalty_second_submission": 2,
                    "penalty_third_submission": 4,
                    "max_submissions_per_analysis": 3,
                    "final_score_strategy": "best",
                    "passing_score": 30,
                },
            )

        biology = courses.get("Inorganic Chemistry WS 2026 - Biology")
        if biology is not None:
            # Per-ion, one attempt (no retries).
            GradingConfig.objects.update_or_create(
                course=biology,
                defaults={
                    "grading_mode": "per_ion",
                    "points_per_correct_ion": 10,
                    "max_submissions_per_analysis": 1,
                    "final_score_strategy": "last",
                    "passing_score": 30,
                },
            )

        # Materials stays on the global default (per-ion) config - no override.

        active_course = None
        for name, _sem, _track, _active, is_the_active in _COURSES:
            if is_the_active:
                active_course = courses.get(name)
        settings_row = AppSettings.get_instance()
        settings_row.points_per_analysis = 10
        settings_row.analyses_per_course = 6
        settings_row.active_course = active_course
        settings_row.save()

    # -- pre-seeded submissions ----------------------------------------------
    def _seed_submissions(
        self, users: dict[str, User], instances: dict[tuple[str, int], list[AnalysisInstance]]
    ) -> None:
        """Grade a handful of submissions through the real submit() logic."""
        plans: list[tuple[str, str, int, str]] = [
            ("student-lena", "Inorganic Chemistry WS 2026 - Chemistry", 1, "correct"),
            ("student-max", "Inorganic Chemistry WS 2026 - Chemistry", 1, "wrong"),
            ("student-anna", "Inorganic Chemistry WS 2026 - Biology", 1, "correct"),
            ("student-ben", "Inorganic Chemistry WS 2026 - Biology", 1, "partial"),
            ("student-mia", "Inorganic Chemistry WS 2026 - Medicine", 1, "correct"),
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
        Seed multiple-choice cards for the demo.

        * Chemistry: a flame-test card (three questions), one open sheet per
          student, two worked submissions.
        * Medicine and Biology: a basic chemistry card (acid/base, amino acids,
          redox), one open sheet per student.
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

        basic_questions = [
            ("Which of these is a strong acid?", ["HCl", "NH3", "NaOH", "H2O"], 0),
            ("A solution with pH 3 is ...", ["acidic", "neutral", "basic", "none of these"], 0),
            ("Which of the following is an amino acid?", ["Glycine", "Glucose", "Glycerol", "Guanine"], 0),
            (
                "In a redox reaction, oxidation is the ...",
                ["loss of electrons", "gain of electrons", "gain of protons", "loss of protons"],
                0,
            ),
        ]

        def make_card(
            course: Course,
            title: str,
            description: str,
            questions: list[tuple[str, list[str], int]],
        ) -> tuple[MCCard, list[MCQuestion]]:
            created: list[MCQuestion] = []
            for text, options, correct_index in questions:
                question = MCQuestion.objects.create(
                    course=course,
                    text=text,
                    description=description,
                    remarks="Demo content for the multiple-choice feature.",
                )
                for i, option in enumerate(options):
                    MCOption.objects.create(
                        question=question, text=option, is_correct=(i == correct_index), sort_order=i
                    )
                created.append(question)
            card = MCCard.objects.create(course=course, title=title, description=description, remarks="Demo card.")
            for i, question in enumerate(created):
                MCCardQuestion.objects.create(card=card, question=question, order=i)
            return card, created

        def make_sheet(card: MCCard, course: Course, students: list[User], number: int = 1) -> MCSheet:
            now = timezone.now().replace(microsecond=0)
            sheet = MCSheet.objects.create(
                card=card,
                course=course,
                window_start=now - timedelta(hours=1),
                window_end=now + timedelta(hours=23),
                number=number,
            )
            for student in students:
                MCStudentAssignment.objects.create(course=course, student=student, sheet=sheet, number=number)
            return sheet

        # Chemistry: flame-test card + two worked submissions.
        chemistry = courses.get("Inorganic Chemistry WS 2026 - Chemistry")
        if chemistry is not None:
            chem_students = [u for u in users.values() if u.is_student and u.course_id == chemistry.id]
            flame_questions = [
                ("Which flame colour does sodium (Na+1) produce?", ["Yellow", "Violet", "Green", "Brick red"], 0),
                ("Which flame colour does copper (Cu+2) produce?", ["Green", "Yellow", "Crimson", "No colour"], 0),
                (
                    "Which flame colour does potassium (K+1) produce?",
                    ["Lilac (violet)", "Yellow", "Green", "Orange"],
                    0,
                ),
            ]
            card, questions = make_card(
                chemistry, "Flame test card", "Three flame-test questions (demo).", flame_questions
            )
            sheet = make_sheet(card, chemistry, chem_students)
            for username, wrong_first in (("student-lena", False), ("student-max", True)):
                student = users.get(username)
                if student is None:
                    continue
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
            self.stdout.write(
                self.style.SUCCESS(
                    f"  multichoice:   chemistry flame-test card, sheet for {len(chem_students)} students"
                )
            )

        # Medicine + Biology: basic chemistry card.
        for course_name in ("Inorganic Chemistry WS 2026 - Medicine", "Inorganic Chemistry WS 2026 - Biology"):
            course = courses.get(course_name)
            if course is None:
                continue
            students = [u for u in users.values() if u.is_student and u.course_id == course.id]
            card, _questions = make_card(
                course, "Basic chemistry card", "Acid/base, amino acids and redox (demo).", basic_questions
            )
            make_sheet(card, course, students)
            short = course_name.split(" - ")[1].lower()
            self.stdout.write(
                self.style.SUCCESS(f"  multichoice:   {short} basic card, sheet for {len(students)} students")
            )

    # -- geology EP monograph example ---------------------------------------
    def _seed_geology_monograph(self, courses: dict[str, Course], users: dict[str, User]) -> None:
        """
        Seed the European Pharmacopoeia monograph multiple-choice card for Geology.

        One card models a monograph analysis on a salt (sodium chloride) with
        three binary sub-tests: identity (true/false), purity (true/false) and
        monograph compliance (complies / does not comply). The course grades the
        card all-or-nothing - the penalty equals the points, so any single wrong
        answer drops the card to zero (the strict "complies / does not comply"
        reading). Two worked submissions exercise the real grading logic (one
        compliant, one not); the remaining student is left unsubmitted.
        """
        from datetime import timedelta

        from django.utils import timezone
        from multichoice.models import MCCard, MCCardQuestion, MCOption, MCQuestion, MCSheet, MCStudentAssignment

        course = courses.get("Inorganic Chemistry WS 2026 - Geology")
        if course is None:
            return
        students = [u for u in users.values() if u.is_student and u.course_id == course.id]
        if not students:
            return

        def make_question(text: str, correct_text: str, other_text: str) -> MCQuestion:
            question = MCQuestion.objects.create(
                course=course,
                text=text,
                description="European Pharmacopoeia monograph sub-test (demo).",
                remarks="Strict binary outcome; the course grades MC cards all-or-nothing.",
            )
            MCOption.objects.create(question=question, text=correct_text, is_correct=True, sort_order=0)
            MCOption.objects.create(question=question, text=other_text, is_correct=False, sort_order=1)
            return question

        questions = [
            make_question("Identity test: is the identity of the salt confirmed?", "true", "false"),
            make_question("Purity test: does the salt meet the purity requirements?", "true", "false"),
            make_question(
                "Monograph test: does the salt comply with the European Pharmacopoeia monograph?",
                "complies",
                "does not comply",
            ),
        ]
        card = MCCard.objects.create(
            course=course,
            title="EP Monograph - Sodium chloride (NaCl)",
            description=(
                "European Pharmacopoeia monograph analysis on sodium chloride: one identity test, a "
                "purity test and a monograph compliance test."
            ),
            remarks=(
                "Results are stated as identity true/false, pure true/false, and complies / does not "
                "comply. Graded all-or-nothing (complies only when every sub-test is correct)."
            ),
        )
        for i, question in enumerate(questions):
            MCCardQuestion.objects.create(card=card, question=question, order=i)

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

        # Two worked examples through the real submit()/grading logic:
        #  - student-david answers every sub-test correctly -> complies (full points)
        #  - student-emma gets the purity sub-test wrong -> does not comply (zero)
        correct = {q.id: q.options_set.get(is_correct=True).id for q in questions}
        for username, wrong_question in (("student-david", None), ("student-emma", questions[1])):
            student = users.get(username)
            if student is None:
                continue
            answers = dict(correct)
            if wrong_question is not None:
                answers[wrong_question.id] = wrong_question.options_set.get(is_correct=False).id
            sheet.submit(student, answers, idempotency_key=f"seed-geo-mc-{student.id}")
        self.stdout.write(
            self.style.SUCCESS(
                f"  EP monograph:  1 card, 3 sub-tests (all-or-nothing), sheet for {len(students)} students"
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
        n_instances = AnalysisInstance.objects.count()
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
        self.stdout.write(f"  substances:     {Substance.objects.count()}  (incl. the Geology CSV salts)")
        self.stdout.write(f"  submissions:    {Submission.objects.count()}")
        self.stdout.write(f"  grading configs:{len(list(GradingConfig.objects.all()))} (global + per-course)")
        self.stdout.write("")
        self.stdout.write(style.NOTICE("Non-Geology announcement windows (relative to now):"))
        for (course_name, number), group in sorted(instances.items()):
            sample = group[0] if group else None
            status = sample.window_status() if sample else "-"
            self.stdout.write(f"  {course_name} #{number}  [{status:>9}]  ({len(group)} students)")
        self.stdout.write("")
        self.stdout.write(style.NOTICE(f"Log in with any demo account and the password '{DEMO_PASSWORD}'."))
