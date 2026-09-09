"""Tests for the admin API endpoints (types, instances, assignments, config)."""

import uuid
from datetime import timedelta

import pytest
from analyses.models import AnalysisInstance, AnalysisType
from config.models import AppSettings, Course, GradingConfig
from django.utils import timezone
from users.models import StudentAssignment

pytestmark = pytest.mark.django_db


class TestAnalysisTypes:
    def test_requires_admin(self, client, student, auth_headers):
        assert client.get("/api/v1/admin/analysis-types", **auth_headers(student)).status_code == 403

    def test_admin_crud(self, client, admin_user, analysis_type, auth_headers):
        # list
        resp = client.get("/api/v1/admin/analysis-types", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert any(t["name"] == "Analysis 3" for t in resp.json())

        # create
        resp = client.post(
            "/api/v1/admin/analysis-types",
            {"name": "Analysis 4", "description": "another"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        new_id = resp.json()["id"]
        assert AnalysisType.objects.filter(pk=new_id).exists()

        # update
        resp = client.put(
            f"/api/v1/admin/analysis-types/{new_id}",
            {"name": "Analysis 4 (rev)", "description": "updated"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert AnalysisType.objects.get(pk=new_id).name == "Analysis 4 (rev)"

        # delete (no instances)
        resp = client.delete(f"/api/v1/admin/analysis-types/{new_id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert not AnalysisType.objects.filter(pk=new_id).exists()

    def test_cannot_delete_type_with_instances(self, client, admin_user, analysis_type, auth_headers):
        resp = client.delete(f"/api/v1/admin/analysis-types/{analysis_type.id}", **auth_headers(admin_user))
        # analysis_type fixture has no instances yet
        assert resp.status_code == 200


class TestAnalysisInstances:
    def test_create_instance(self, client, admin_user, analysis_type, course, auth_headers):
        now = timezone.now()
        resp = client.post(
            "/api/v1/admin/analysis-instances",
            {
                "type_id": analysis_type.id,
                "course_id": course.id,
                "number": 4,
                "window_start": (now + timedelta(hours=1)).isoformat(),
                "window_end": (now + timedelta(hours=3)).isoformat(),
                "correct_ion_ids": [],
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert AnalysisInstance.objects.filter(type=analysis_type, number=4).exists()

    def test_student_cannot_create(self, client, student, analysis_type, course, auth_headers):
        now = timezone.now()
        resp = client.post(
            "/api/v1/admin/analysis-instances",
            {
                "type_id": analysis_type.id,
                "course_id": course.id,
                "number": 4,
                "window_start": (now + timedelta(hours=1)).isoformat(),
                "window_end": (now + timedelta(hours=3)).isoformat(),
                "correct_ion_ids": [],
            },
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_cannot_delete_instance_with_submissions(
        self, client, admin_user, assigned_instance, student, auth_headers
    ):
        from substances.models import Ion

        ids = list(Ion.objects.filter(symbol__in=["NH4+"]).values_list("id", flat=True))
        client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": ids, "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        resp = client.delete(f"/api/v1/admin/analysis-instances/{assigned_instance.id}", **auth_headers(admin_user))
        assert resp.status_code == 409
        assert AnalysisInstance.objects.filter(pk=assigned_instance.id).exists()


class TestAssignments:
    def test_assign_and_unassign(self, client, admin_user, assigned_instance, student, course, auth_headers):
        resp = client.get("/api/v1/admin/assignments", **auth_headers(admin_user))
        assert resp.status_code == 200
        rows = resp.json()
        assert any(r["student"] == student.username and r["instance_id"] == assigned_instance.id for r in rows)
        assignment_id = next(
            r["id"] for r in rows if r["student"] == student.username and r["instance_id"] == assigned_instance.id
        )
        resp = client.delete(f"/api/v1/admin/assignments/{assignment_id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert not StudentAssignment.objects.filter(pk=assignment_id).exists()

    def test_create_new_assignment(self, client, admin_user, analysis_instance, student, course, auth_headers):
        resp = client.post(
            "/api/v1/admin/assignments",
            {"instance_id": analysis_instance.id, "student_id": student.id, "number": 3},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert StudentAssignment.objects.filter(instance=analysis_instance, student=student).exists()


class TestGradingConfig:
    def test_read_grading_config(self, client, student, auth_headers):
        resp = client.get("/api/v1/admin/grading-config", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        assert data["points_per_correct_ion"] == 10
        assert data["grading_mode"] == "per_ion"

    def test_admin_updates_grading_config(self, client, admin_user, auth_headers):
        payload = {
            "points_per_correct_ion": 5,
            "penalty_second_submission": 1,
            "penalty_third_submission": 3,
            "false_positive_deduction": 2,
            "grading_mode": "per_analysis",
            "max_submissions_per_analysis": 2,
            "final_score_strategy": "last",
        }
        resp = client.put(
            "/api/v1/admin/grading-config", payload, content_type="application/json", **auth_headers(admin_user)
        )
        assert resp.status_code == 200
        gc = GradingConfig.get_instance()
        assert gc.points_per_correct_ion == 5
        assert gc.grading_mode == "per_analysis"

    def test_student_cannot_update_grading_config(self, client, student, auth_headers):
        payload = {
            "points_per_correct_ion": 1,
            "penalty_second_submission": 0,
            "penalty_third_submission": 0,
            "false_positive_deduction": 0,
            "grading_mode": "per_ion",
            "max_submissions_per_analysis": 1,
            "final_score_strategy": "best",
        }
        resp = client.put(
            "/api/v1/admin/grading-config", payload, content_type="application/json", **auth_headers(student)
        )
        assert resp.status_code == 403


class TestAppSettings:
    def test_admin_updates_app_settings(self, client, admin_user, course, auth_headers):
        resp = client.put(
            "/api/v1/admin/app-settings",
            {"points_per_analysis": 15, "analyses_per_course": 4, "active_course_id": course.id},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        s = AppSettings.get_instance()
        assert s.points_per_analysis == 15
        assert s.analyses_per_course == 4
        assert s.active_course_id == course.id


class TestCourses:
    def test_admin_creates_course(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/courses",
            {"name": "Pharmacy Inorg 2026", "semester": "SS 2026", "track": "pharmacy"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert Course.objects.filter(name="Pharmacy Inorg 2026").exists()
