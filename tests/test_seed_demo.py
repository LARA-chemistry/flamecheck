"""
Tests for the ``seed_demo`` management command (staging demo data via factories).

Covers:
- the seeded counts (courses, users by role, analysis types, instances,
  assignments, barcodes, submissions, grading configs),
- the uniform demo password (``FlameCheck32!``) is set and hashed for every
  account,
- the announcement windows span the open / too_early / too_late / submitted
  states,
- the per-course grading overrides (Biology, Pharmacy) are present alongside
  the global default,
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
from substances.models import Ion, Substance
from users.models import StudentAssignment, StudentBarcode, User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _seeded(db) -> None:
    """Run ``seed_demo`` once for every test in this module (fresh test DB)."""
    call_command("seed_demo", stdout=StringIO())


class TestSeedCounts:
    """The command seeds the expected volume of demo data."""

    def test_courses(self):
        assert Course.objects.count() == 4
        assert Course.objects.filter(name="Inorganic Chemistry WS 2026 - Chemistry").exists()
        assert Course.objects.filter(name="Inorganic Chemistry WS 2026 - Biology").exists()

    def test_users_by_role(self):
        assert User.objects.filter(username="admin", role="admin").count() == 1
        assert User.objects.filter(role="assistant").count() == 3
        assert User.objects.filter(role="student").count() == 12

    def test_analysis_types(self):
        assert AnalysisType.objects.count() == 3
        # Every type has a non-empty possible-ion set.
        for t in AnalysisType.objects.all():
            assert t.possible_ions.count() > 0

    def test_instances_one_per_student_per_announcement(self):
        # Each student gets one dedicated instance per announcement in their
        # course: Chemistry 2x3 + Biology 3x3 + Pharmacy 2x3 + Materials 2x3
        # = 27 instances.
        assert AnalysisInstance.objects.count() == 27
        assert StudentAssignment.objects.count() == 27
        # No student has two instances for the same (course, number).
        dupes = StudentAssignment.objects.values("student", "course", "number").annotate(n=Count("id")).filter(n__gt=1)
        assert dupes.count() == 0

    def test_barcodes_for_every_student(self):
        assert StudentBarcode.objects.count() == 12
        for student in User.objects.filter(role="student"):
            assert student.barcodes.count() == 1

    def test_catalog_seeded(self):
        assert Ion.objects.count() >= 20
        assert Substance.objects.count() >= 10

    def test_grading_configs_global_plus_per_course(self):
        # One global default + per-course overrides (Biology, Pharmacy).
        assert GradingConfig.objects.count() == 3
        assert GradingConfig.objects.filter(course__isnull=True).count() == 1
        biology = Course.objects.get(name="Inorganic Chemistry WS 2026 - Biology")
        assert GradingConfig.objects.filter(course=biology).exists()
        pharmacy = Course.objects.get(name="Inorganic Chemistry WS 2026 - Pharmacy")
        # The Pharmacy override is the all-or-nothing MC grading (penalty == points).
        pharma_cfg = GradingConfig.objects.get(course=pharmacy)
        assert pharma_cfg.mc_penalty_per_wrong == pharma_cfg.mc_points_per_card

    def test_app_settings_active_course(self):
        # Chemistry is the default (active) course.
        settings_row = AppSettings.get_instance()
        assert settings_row.active_course is not None
        assert settings_row.active_course.name == "Inorganic Chemistry WS 2026 - Chemistry"

    def test_assistant_course_links(self):
        # Each of the three assistants is linked to a course.
        assert AssistantCourse.objects.count() == 3


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

    def test_per_course_grading_applied_to_biology(self):
        biology = Course.objects.get(name="Inorganic Chemistry WS 2026 - Biology")
        anna = User.objects.get(username="student-anna")
        instance = next(
            i for i in AnalysisInstance.objects.filter(course=biology) if i.assignments.filter(student=anna).exists()
        )
        # Biology uses per_analysis (all-or-nothing): a full-match submission
        # scores the flat per_analysis points, not per-ion points.
        sub = Submission.objects.get(analysis_instance=instance, student=anna)
        config = GradingConfig.get_for_course(biology)
        assert config.grading_mode == "per_analysis"
        assert sub.score == config.points_per_correct_ion


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
        }
        assert before == after


class TestReset:
    """--reset wipes the seeded domain before re-seeding."""

    def test_reset_wipes_then_reseeds(self):
        # Seed once so there is something to reset.
        call_command("seed_demo", stdout=StringIO())
        assert Submission.objects.count() == 6
        assert AnalysisInstance.objects.count() == 27
        # Reset + re-seed: same end state, no accumulation.
        call_command("seed_demo", "--reset", stdout=StringIO())
        assert Submission.objects.count() == 6
        assert AnalysisInstance.objects.count() == 27
        assert Course.objects.count() == 4
        assert User.objects.filter(role="student").count() == 12
