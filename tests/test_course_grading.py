"""
Tests for per-course grading configuration.

Covers:
- ``GradingConfig.get_for_course`` falling back to the global default.
- ``AnalysisInstance`` scoring using the course's own config when present and
  the global default otherwise.
- The per-course admin endpoints (GET fallback, PUT create/update, auth, 404).
- The all-or-nothing ``per_analysis`` scoring mode.
- The course total + passing-score business logic (``student_course_result``).
"""

from __future__ import annotations

import pytest
from analyses.factory import AnalysisInstanceFactory, AnalysisTypeFactory
from analyses.models import AnalysisInstance, student_course_result
from config.factory import CourseFactory, GradingConfigFactory
from config.models import GradingConfig
from substances.factory import IonFactory
from users.factory import StudentAssignmentFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def grading_global():
    """The global (default) grading configuration."""
    return GradingConfigFactory()


@pytest.fixture
def course():
    return CourseFactory(name="Per-course grading course")


@pytest.fixture
def course_with_config(course):
    """A course that has its own grading configuration."""
    GradingConfigFactory(course=course, points_per_correct_ion=25, max_submissions_per_analysis=5)
    return course


class TestGetForCourse:
    def test_falls_back_to_global_when_no_course_config(self, grading_global, course):
        assert GradingConfig.get_for_course(course).pk == grading_global.pk

    def test_returns_course_config_when_present(self, course_with_config):
        gc = GradingConfig.get_for_course(course_with_config)
        assert gc.course_id == course_with_config.id
        assert gc.points_per_correct_ion == 25

    def test_none_course_returns_global(self, grading_global):
        assert GradingConfig.get_for_course(None).pk == grading_global.pk


class TestInstanceUsesCourseConfig:
    def _instance(self, course):
        type_ = AnalysisTypeFactory(name=f"Type-{course.id}")
        return AnalysisInstanceFactory(type=type_, course=course)

    def test_uses_course_config_max_submissions(self, course_with_config):
        instance = self._instance(course_with_config)
        assert instance.submission_limit() == 5  # from course config, not global default of 3

    def test_falls_back_to_global_max_submissions(self, grading_global, course):
        instance = self._instance(course)
        assert instance.submission_limit() == grading_global.max_submissions_per_analysis

    def test_ideal_score_uses_course_points_per_ion(self, course_with_config):
        gc = GradingConfig.get_for_course(course_with_config)
        assert gc.points_per_correct_ion == 25
        # With no correct ions set, ideal is 0 regardless of the multiplier.
        assert self._instance(course_with_config).ideal_score() == 0


class TestPerCourseGradingEndpoint:
    @staticmethod
    def _payload(**overrides) -> dict:
        """A full grading payload (the form always sends all eight fields)."""
        base = {
            "points_per_correct_ion": 30,
            "penalty_second_submission": 2,
            "penalty_third_submission": 4,
            "false_positive_deduction": 0,
            "grading_mode": "per_ion",
            "max_submissions_per_analysis": 3,
            "final_score_strategy": "best",
            "passing_score": 50,
        }
        base.update(overrides)
        return base

    def test_get_401_when_unauthenticated(self, client):
        resp = client.get("/api/v1/admin/courses/1/grading-config")
        assert resp.status_code == 401

    def test_get_falls_back_to_global(self, client, admin_user, grading_global, course, auth_headers):
        resp = client.get(
            f"/api/v1/admin/courses/{course.id}/grading-config",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["points_per_correct_ion"] == grading_global.points_per_correct_ion

    def test_put_403_for_non_admin(self, client, student, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/courses/{course.id}/grading-config",
            self._payload(),
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_put_creates_course_config(self, client, admin_user, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/courses/{course.id}/grading-config",
            self._payload(points_per_correct_ion=30),
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        assert resp.json()["points_per_correct_ion"] == 30
        # A course-specific row now exists and is returned by get_for_course.
        gc = GradingConfig.get_for_course(course)
        assert gc.course_id == course.id
        assert gc.points_per_correct_ion == 30
        # The global default is untouched.
        assert GradingConfig.get_instance().course_id is None

    def test_put_404_for_unknown_course(self, client, admin_user, auth_headers):
        resp = client.put(
            "/api/v1/admin/courses/99999/grading-config",
            self._payload(),
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_put_stores_passing_score(self, client, admin_user, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/courses/{course.id}/grading-config",
            self._payload(passing_score=75),
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        assert resp.json()["passing_score"] == 75
        gc = GradingConfig.get_for_course(course)
        assert gc.passing_score == 75

    def test_get_includes_passing_score(self, client, admin_user, grading_global, course, auth_headers):
        grading_global.passing_score = 42
        grading_global.save()
        resp = client.get(
            f"/api/v1/admin/courses/{course.id}/grading-config",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["passing_score"] == 42


class TestPerAnalysisScoring:
    """The all-or-nothing 'per_analysis' grading mode (per course or global)."""

    @staticmethod
    def _instance_with_student(course, *, correct_count, extra_count=0):
        """
        Create an open instance with ``correct_count`` correct ions.

        The instance gets ``correct_count`` correct ions plus ``extra_count``
        distractors and an assigned student.

        Returns:
            tuple: ``(instance, student, correct_ids, extra_ids)``.

        """
        type_ = AnalysisTypeFactory(name=f"Type-{course.id}-{correct_count}-{extra_count}")
        instance = AnalysisInstanceFactory(type=type_, course=course)
        student = UserFactory(course=course)
        StudentAssignmentFactory(student=student, instance=instance, course=course, number=1)

        ions = [IonFactory(symbol=f"K{type_.id}{n}+") for n in range(correct_count)]
        extras = [IonFactory(symbol=f"X{type_.id}{n}") for n in range(extra_count)]
        instance.correct_ions.set(ions)
        type_.possible_ions.set(ions + extras)
        return instance, student, [i.id for i in ions], [i.id for i in extras]

    @staticmethod
    def _per_analysis(grading_global, *, points=20, penalty_second=0):
        """Point the global config at per-analysis scoring."""
        grading_global.grading_mode = "per_analysis"
        grading_global.points_per_correct_ion = points
        grading_global.penalty_second_submission = penalty_second
        grading_global.save()

    def test_exact_match_awards_full_points(self, course, grading_global):
        self._per_analysis(grading_global, points=20)
        instance, student, correct_ids, _ = self._instance_with_student(course, correct_count=3)
        result = instance.submit(student, correct_ids, idempotency_key="k1")
        assert result.score == 20
        assert result.ideal_score == 20

    def test_inexact_match_scores_zero(self, course, grading_global):
        self._per_analysis(grading_global, points=20)
        instance, student, correct_ids, _ = self._instance_with_student(course, correct_count=3)
        # Miss one ion -> all-or-nothing means zero.
        result = instance.submit(student, correct_ids[:2], idempotency_key="k1")
        assert result.score == 0
        assert result.ideal_score == 20

    def test_extra_ion_scores_zero(self, course, grading_global):
        self._per_analysis(grading_global, points=20)
        instance, student, correct_ids, extra_ids = self._instance_with_student(course, correct_count=2, extra_count=1)
        result = instance.submit(student, correct_ids + extra_ids, idempotency_key="k1")
        assert result.score == 0

    def test_no_retry_penalty_in_per_analysis(self, course, grading_global):
        """A 2nd exact submission is not penalised (penalties are per-ion only)."""
        self._per_analysis(grading_global, points=20, penalty_second=5)
        instance, student, correct_ids, _ = self._instance_with_student(course, correct_count=2)
        instance.submit(student, correct_ids, idempotency_key="k1")
        result = instance.submit(student, correct_ids, idempotency_key="k2")
        assert result.score == 20
        assert result.penalty == 0

    def test_per_course_mode_overrides_global(self, course, grading_global):
        """A course in per_ion mode scores per ion even though global is per_analysis."""
        self._per_analysis(grading_global, points=20)
        GradingConfig.objects.create(course=course, grading_mode="per_ion", points_per_correct_ion=10)
        instance, student, correct_ids, _ = self._instance_with_student(course, correct_count=3)
        result = instance.submit(student, correct_ids[:2], idempotency_key="k1")
        # Two of three correct ions -> 2 x 10 = 20, not all-or-nothing.
        assert result.score == 20


class TestStudentCourseResult:
    """The course total + passing-score business logic."""

    @staticmethod
    def _enroll(course, count) -> tuple:
        """Enroll a fresh student in ``count`` open instances of ``course``."""
        type_ = AnalysisTypeFactory(name=f"ResType-{course.id}")
        student = UserFactory(course=course)
        for n in range(count):
            instance = AnalysisInstanceFactory(type=type_, course=course, number=n + 1)
            StudentAssignmentFactory(student=student, instance=instance, course=course, number=n + 1)
        return student, list(AnalysisInstance.objects.for_student(student))

    def test_zero_submissions_not_passed(self, course, grading_global):
        grading_global.passing_score = 30
        grading_global.save()
        student, instances = self._enroll(course, 3)
        result = student_course_result(student)
        assert result["instances"] == instances
        assert result["total_score"] == 0
        assert result["passing_score"] == 30
        assert result["passed"] is False

    def test_passed_when_total_reaches_passing_score(self, course, grading_global):
        """Two exact submissions (2 x 10 = 20) clear a passing score of 15."""
        grading_global.passing_score = 15
        grading_global.save()
        student, instances = self._enroll(course, 2)
        for instance in instances:
            ion = IonFactory(symbol=f"P{instance.id}+")
            instance.correct_ions.set([ion])
            instance.type.possible_ions.set([ion])
            instance.submit(student, [ion.id], idempotency_key=f"key-{instance.id}")
        result = student_course_result(student)
        assert result["total_score"] == 20
        assert result["ideal_score"] == 20
        assert result["passed"] is True

    def test_per_course_passing_score_overrides_global(self, course, grading_global):
        """The course's own passing score wins over the global default."""
        grading_global.passing_score = 100  # unreachable via the global row
        grading_global.save()
        GradingConfig.objects.create(course=course, passing_score=10, points_per_correct_ion=10)
        student, instances = self._enroll(course, 1)
        ion = IonFactory(symbol=f"Q{instances[0].id}+")
        instances[0].correct_ions.set([ion])
        instances[0].type.possible_ions.set([ion])
        instances[0].submit(student, [ion.id], idempotency_key="q1")
        result = student_course_result(student)
        assert result["passing_score"] == 10
        assert result["total_score"] == 10
        assert result["passed"] is True

    def test_zero_passing_score_always_passes(self, course, grading_global):
        grading_global.passing_score = 0
        grading_global.save()
        student, _ = self._enroll(course, 1)
        result = student_course_result(student)
        assert result["passed"] is True
