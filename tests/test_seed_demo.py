"""
Tests for the ``seed_demo`` management command (staging demo data via factories).

Covers:
- the seeded counts (courses, users by role, analysis types, instances,
  assignments, barcodes, submissions, grading configs),
- the uniform demo password (``FlameCheck32!``) is set and hashed for every
  account,
- the Geology showcase: the CSV salts are imported, each student gets the full
  task programme with a per-student label and a valid (subset) answer key, and
  the per-analysis retry-penalty grading config is in place,
- the Pharmacy showcase: the same CSV-salt programme with the pharmacy task
  names, the per-salt EP monograph multiple-choice cards, and the per-analysis
  grading config (10 / 8 / 6, min points to pass 30),
- the announcement windows span the open / too_early / too_late / submitted
  states,
- the per-course grading overrides (Geology, Pharmacy, Chemistry, Medicine,
  Biology) are present alongside the global default (Materials stays on the
  global config),
- idempotency (re-running does not duplicate rows),
- ``--reset`` wiping the seeded domain before re-seeding.
"""

from __future__ import annotations

from io import StringIO

import pytest
from analyses.management.commands.seed_demo import _USERS, DEMO_PASSWORD
from analyses.models import AnalysisInstance, AnalysisType, Submission
from config.models import AppSettings, AssistantCourse, Course, GradingConfig
from django.core.management import call_command
from django.db.models import Count
from multichoice.models import MCCard, MCQuestion, MCSheet, MCStudentAssignment, MCSubmission
from substances.models import Ion, Substance
from users.models import StudentAssignment, StudentBarcode, User

pytestmark = pytest.mark.django_db

_COURSES = [
    "Inorganic Chemistry WS 2026 - Chemistry",
    "Inorganic Chemistry WS 2026 - Biology",
    "Inorganic Chemistry WS 2026 - Geology",
    "Inorganic Chemistry WS 2026 - Medicine",
    "Inorganic Chemistry WS 2026 - Pharmacy",
    "Inorganic Chemistry SS 2026 - Materials",
]

_PHARMACY_TYPES = [
    "Practice Analysis (1 Salt)",
    "Analysis 1 (2 Salts)",
    "Analysis 2 (max. 3 Salts)",
    "Analysis 3 (max. 3 Salts)",
    "Analysis 4 (max. 4 Salts)",
    "Analysis 5 (max. 4 Salts)",
    "European Pharmacopoeia Monography Analyses",
]


@pytest.fixture(autouse=True)
def _seeded(db) -> None:
    """Run ``seed_demo`` once for every test in this module (fresh test DB)."""
    call_command("seed_demo", stdout=StringIO())


class TestSeedCounts:
    """The command seeds the expected volume of demo data."""

    def test_courses(self):
        assert Course.objects.count() == 6
        for name in _COURSES:
            assert Course.objects.filter(name=name).exists()

    def test_users_by_role(self):
        assert User.objects.filter(username="admin", role="admin").count() == 1
        assert User.objects.filter(role="assistant").count() == 6
        assert User.objects.filter(role="student").count() == 18

    def test_students_have_integer_labspace_ids(self):
        # Students carry an integer labspace id (1, 2, 3, ...) within their course.
        geology = Course.objects.get(name="Inorganic Chemistry WS 2026 - Geology")
        students = User.objects.filter(course=geology, role="student")
        assert {s.labspace_id for s in students} == {"1", "2", "3"}

    def test_analysis_types(self):
        # 3 shared + 3 medicine + 6 geology + 6 pharmacy + 1 pharmacy monograph
        # = 19 types.
        assert AnalysisType.objects.count() == 19
        # Every type has a non-empty possible-ion set.
        for t in AnalysisType.objects.all():
            assert t.possible_ions.count() > 0

    def test_instances_one_per_student_per_announcement(self):
        # Geology 6x3 + Pharmacy 6x3 + Chemistry 2x3 + Biology 2x3 + Medicine
        # 3x3 + Materials 2x3 = 63 instances.
        assert AnalysisInstance.objects.count() == 63
        assert StudentAssignment.objects.count() == 63
        # No student has two instances for the same (course, number).
        dupes = StudentAssignment.objects.values("student", "course", "number").annotate(n=Count("id")).filter(n__gt=1)
        assert dupes.count() == 0

    def test_geology_instance_labels(self):
        # Each Geology instance is labelled "<type, no spaces>_<labspace_id>".
        geology = Course.objects.get(name="Inorganic Chemistry WS 2026 - Geology")
        labels = set(AnalysisInstance.objects.filter(course=geology).values_list("label", flat=True))
        assert "PracticeAnalysis_1" in labels
        assert "Analysis1_2" in labels
        assert "Analysis5_3" in labels

    def test_geology_answer_keys_are_valid_subsets(self):
        # Every Geology answer key is a non-empty subset of its type's scope.
        geology = Course.objects.get(name="Inorganic Chemistry WS 2026 - Geology")
        for inst in AnalysisInstance.objects.filter(course=geology).prefetch_related(
            "correct_ions", "type__possible_ions"
        ):
            possible = set(inst.type.possible_ions.values_list("id", flat=True))
            correct = set(inst.correct_ions.values_list("id", flat=True))
            assert correct, f"{inst.label} has an empty answer key"
            assert correct.issubset(possible)

    def test_barcodes_for_every_student(self):
        assert StudentBarcode.objects.count() == 18
        for student in User.objects.filter(role="student"):
            assert student.barcodes.count() == 1

    def test_catalog_seeded(self):
        assert Ion.objects.count() >= 30
        # 18 base substances + 64 CSV salts (merged by name) -> well over 70.
        assert Substance.objects.count() >= 70

    def test_geology_imports_csv_salts(self):
        # The Geology showcase imports the salts from examples/substance_list.csv
        # on top of the base substances.
        assert Substance.objects.filter(name="Sodium chloride").exists()
        assert Substance.objects.filter(name__icontains="acetate").count() >= 5

    def test_grading_configs_global_plus_per_course(self):
        # One global default + per-course overrides (Geology, Pharmacy, Chemistry,
        # Medicine, Biology). Materials stays on the global config (no override).
        assert GradingConfig.objects.count() == 6
        assert GradingConfig.objects.filter(course__isnull=True).count() == 1
        for name in ("Biology", "Geology", "Pharmacy", "Chemistry", "Medicine"):
            course = Course.objects.get(name=f"Inorganic Chemistry WS 2026 - {name}")
            assert GradingConfig.objects.filter(course=course).exists()
        materials = Course.objects.get(name="Inorganic Chemistry SS 2026 - Materials")
        assert not GradingConfig.objects.filter(course=materials).exists()

    def test_geology_grading_is_per_analysis_with_retry_penalty(self):
        geology = Course.objects.get(name="Inorganic Chemistry WS 2026 - Geology")
        cfg = GradingConfig.get_for_course(geology)
        assert cfg.grading_mode == "per_analysis"
        assert cfg.points_per_correct_ion == 10
        assert cfg.penalty_second_submission == 2
        assert cfg.penalty_third_submission == 4
        assert cfg.max_submissions_per_analysis == 3
        assert cfg.passing_score == 30

    def test_app_settings_active_course(self):
        # Geology is the default (active) course.
        settings_row = AppSettings.get_instance()
        assert settings_row.active_course is not None
        assert settings_row.active_course.name == "Inorganic Chemistry WS 2026 - Geology"

    def test_assistant_course_links(self):
        # Each of the six assistants is linked to a course.
        assert AssistantCourse.objects.count() == 6


class TestDemoPassword:
    """Every demo account shares the uniform (hashed) password."""

    def test_all_users_have_demo_password(self):
        usernames = [u[0] for u in _USERS]
        for user in User.objects.filter(username__in=usernames):
            assert user.check_password(DEMO_PASSWORD)
            # The stored value is a hash, never the cleartext password.
            assert DEMO_PASSWORD not in user.password

    def test_admin_is_staff_and_superuser(self):
        admin = User.objects.get(username="admin")
        assert admin.is_staff and admin.is_superuser and admin.role == "admin"


class TestWindowStates:
    """The announcement windows cover the full state spectrum."""

    def test_window_states_present(self):
        statuses = {i.window_status() for i in AnalysisInstance.objects.all()}
        # open (unsubmitted, in-window), too_early, too_late, and submitted
        # (the pre-seeded submissions mark some instances as submitted).
        assert "open" in statuses
        assert "too_early" in statuses
        assert "too_late" in statuses
        assert "submitted" in statuses


class TestSubmissions:
    """Pre-seeded submissions are graded through the real submit() logic."""

    def test_submissions_created_and_graded(self):
        subs = list(Submission.objects.all())
        assert len(subs) == 6
        # The "correct" plans score the full ideal score for their course.
        assert any(s.score == s.ideal_score and s.wrong_count == 0 for s in subs)
        # The "partial" plans score below the ideal (missed ions).
        assert any(0 < s.score < s.ideal_score for s in subs)

    def test_per_analysis_grading_applied_to_medicine(self):
        medicine = Course.objects.get(name="Inorganic Chemistry WS 2026 - Medicine")
        mia = User.objects.get(username="student-mia")
        instance = next(
            i for i in AnalysisInstance.objects.filter(course=medicine) if i.assignments.filter(student=mia).exists()
        )
        sub = Submission.objects.get(analysis_instance=instance, student=mia)
        config = GradingConfig.get_for_course(medicine)
        # Medicine uses per_analysis (all-or-nothing): a full match scores the
        # flat per-analysis points.
        assert config.grading_mode == "per_analysis"
        assert sub.score == config.points_per_correct_ion

    def test_per_ion_grading_applied_to_biology(self):
        biology = Course.objects.get(name="Inorganic Chemistry WS 2026 - Biology")
        anna = User.objects.get(username="student-anna")
        instance = next(
            i for i in AnalysisInstance.objects.filter(course=biology) if i.assignments.filter(student=anna).exists()
        )
        sub = Submission.objects.get(analysis_instance=instance, student=anna)
        config = GradingConfig.get_for_course(biology)
        # Biology uses per-ion, one attempt: anna submitted all 4 correct ions.
        assert config.grading_mode == "per_ion"
        assert sub.score == 4 * config.points_per_correct_ion


class TestPharmacySeed:
    """The Pharmacy showcase: CSV-salt programme + per-salt EP monograph cards."""

    def test_types_and_scopes(self):
        # All seven pharmacy tasks exist with the syllabus ion scopes.
        types = {t.name: t for t in AnalysisType.objects.all()}
        for name in _PHARMACY_TYPES:
            assert name in types, name
        assert types["Practice Analysis (1 Salt)"].possible_ions.count() == 6
        assert types["Analysis 1 (2 Salts)"].possible_ions.count() == 6
        assert types["Analysis 2 (max. 3 Salts)"].possible_ions.count() == 11
        assert types["Analysis 3 (max. 3 Salts)"].possible_ions.count() == 22
        assert types["Analysis 4 (max. 4 Salts)"].possible_ions.count() == 11
        assert types["Analysis 5 (max. 4 Salts)"].possible_ions.count() == 33
        assert types["European Pharmacopoeia Monography Analyses"].possible_ions.count() == 33

    def test_labspace_ids_start_at_one(self):
        # Pharmacy students carry integer labspace ids starting from 1.
        pharmacy = Course.objects.get(name="Inorganic Chemistry WS 2026 - Pharmacy")
        students = User.objects.filter(course=pharmacy, role="student")
        assert {s.labspace_id for s in students} == {"1", "2", "3"}

    def test_instances_with_valid_answer_keys(self):
        # 6 analysis tasks x 3 students = 18 instances; the monograph task has
        # no instances (it is run as multiple-choice cards).
        pharmacy = Course.objects.get(name="Inorganic Chemistry WS 2026 - Pharmacy")
        instances = AnalysisInstance.objects.filter(course=pharmacy)
        assert instances.count() == 18
        mono = AnalysisType.objects.get(name="European Pharmacopoeia Monography Analyses")
        assert not instances.filter(type=mono).exists()
        assert "PracticeAnalysis(1Salt)_1" in instances.values_list("label", flat=True)
        for inst in instances.prefetch_related("correct_ions", "type__possible_ions"):
            possible = set(inst.type.possible_ions.values_list("id", flat=True))
            correct = set(inst.correct_ions.values_list("id", flat=True))
            assert correct, f"{inst.label} has an empty answer key"
            assert correct.issubset(possible)
            assert inst.assigned_substances.count() >= 1

    def test_ep_monograph_cards_per_salt(self):
        # One "EP Monograph - <salt>" card per CSV salt, each with the three
        # shared sub-test questions and one open sheet for all students.
        pharmacy = Course.objects.get(name="Inorganic Chemistry WS 2026 - Pharmacy")
        cards = MCCard.objects.filter(course=pharmacy)
        assert cards.count() == 64
        assert all(c.title.startswith("EP Monograph - ") for c in cards)
        assert len({c.title for c in cards}) == 64
        assert MCQuestion.objects.filter(course=pharmacy).count() == 3
        for card in cards:
            assert [q.text for q in card.questions()] == [
                "Does the salt pass the identity test?",
                "Is the salt pure?",
                "Does it meet the monograph requirements?",
            ]
        assert MCSheet.objects.filter(course=pharmacy).count() == 64
        assert MCStudentAssignment.objects.filter(course=pharmacy).count() == 64 * 3

    def test_worked_submissions_graded(self):
        pharmacy = Course.objects.get(name="Inorganic Chemistry WS 2026 - Pharmacy")
        subs = list(MCSubmission.objects.filter(sheet__course=pharmacy))
        assert len(subs) == 2
        # One fully compliant card (10/10) and one failed purity test (10 - 2).
        assert sorted(s.score for s in subs) == [8, 10]
        assert all(s.ideal_score == 10 for s in subs)

    def test_grading_config(self):
        pharmacy = Course.objects.get(name="Inorganic Chemistry WS 2026 - Pharmacy")
        cfg = GradingConfig.get_for_course(pharmacy)
        assert cfg.grading_mode == "per_analysis"
        assert cfg.points_per_correct_ion == 10
        assert cfg.penalty_second_submission == 2
        assert cfg.penalty_third_submission == 4
        assert cfg.max_submissions_per_analysis == 3
        assert cfg.passing_score == 30
        assert cfg.mc_points_per_card == 10
        assert cfg.mc_penalty_per_wrong == 2


class TestIdempotency:
    """Re-running the command does not duplicate the seeded rows."""

    def test_re_run_is_idempotent(self):
        call_command("seed_demo", stdout=StringIO())
        before = {
            "courses": Course.objects.count(),
            "users": User.objects.count(),
            "types": AnalysisType.objects.count(),
            "instances": AnalysisInstance.objects.count(),
            "assignments": StudentAssignment.objects.count(),
            "barcodes": StudentBarcode.objects.count(),
            "submissions": Submission.objects.count(),
            "mc_questions": MCQuestion.objects.count(),
            "mc_cards": MCCard.objects.count(),
            "mc_sheets": MCSheet.objects.count(),
            "mc_assignments": MCStudentAssignment.objects.count(),
            "mc_submissions": MCSubmission.objects.count(),
        }
        call_command("seed_demo", stdout=StringIO())
        after = {
            "courses": Course.objects.count(),
            "users": User.objects.count(),
            "types": AnalysisType.objects.count(),
            "instances": AnalysisInstance.objects.count(),
            "assignments": StudentAssignment.objects.count(),
            "barcodes": StudentBarcode.objects.count(),
            "submissions": Submission.objects.count(),
            "mc_questions": MCQuestion.objects.count(),
            "mc_cards": MCCard.objects.count(),
            "mc_sheets": MCSheet.objects.count(),
            "mc_assignments": MCStudentAssignment.objects.count(),
            "mc_submissions": MCSubmission.objects.count(),
        }
        assert before == after


class TestReset:
    """--reset wipes the seeded domain before re-seeding."""

    def test_reset_wipes_then_reseeds(self):
        # Seed once so there is something to reset.
        call_command("seed_demo", stdout=StringIO())
        assert Submission.objects.count() == 6
        assert AnalysisInstance.objects.count() == 63
        # Reset + re-seed: same end state, no accumulation.
        call_command("seed_demo", "--reset", stdout=StringIO())
        assert Submission.objects.count() == 6
        assert AnalysisInstance.objects.count() == 63
        assert Course.objects.count() == 6
        assert User.objects.filter(role="student").count() == 18
