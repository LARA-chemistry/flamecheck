"""
Tests for per-course grading configuration.

Covers:
- ``GradingConfig.get_for_course`` falling back to the global default.
- ``AnalysisInstance`` scoring using the course's own config when present and
  the global default otherwise.
- The per-course admin endpoints (GET fallback, PUT create/update, auth, 404).
"""

from __future__ import annotations

import pytest
from analyses.factory import AnalysisInstanceFactory, AnalysisTypeFactory
from config.factory import CourseFactory, GradingConfigFactory
from config.models import GradingConfig

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
        """A full grading payload (the form always sends all seven fields)."""
        base = {
            "points_per_correct_ion": 30,
            "penalty_second_submission": 2,
            "penalty_third_submission": 4,
            "false_positive_deduction": 0,
            "grading_mode": "per_ion",
            "max_submissions_per_analysis": 3,
            "final_score_strategy": "best",
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
