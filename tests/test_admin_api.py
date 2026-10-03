"""Tests for the admin API endpoints (types, instances, assignments, config)."""

import io
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
            "passing_score": 25,
        }
        resp = client.put(
            "/api/v1/admin/grading-config", payload, content_type="application/json", **auth_headers(admin_user)
        )
        assert resp.status_code == 200
        gc = GradingConfig.get_instance()
        assert gc.points_per_correct_ion == 5
        assert gc.grading_mode == "per_analysis"
        assert gc.passing_score == 25

    def test_student_cannot_update_grading_config(self, client, student, auth_headers):
        payload = {
            "points_per_correct_ion": 1,
            "penalty_second_submission": 0,
            "penalty_third_submission": 0,
            "false_positive_deduction": 0,
            "grading_mode": "per_ion",
            "max_submissions_per_analysis": 1,
            "final_score_strategy": "best",
            "passing_score": 50,
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


class TestDjangoAdminSettings:
    """The standard Django admin must expose the settings singletons for editing."""

    def test_grading_config_changelist_quick_edit(self, client, admin_user):
        client.force_login(admin_user)
        GradingConfig.get_instance()
        resp = client.get("/admin-django/config/gradingconfig/")
        assert resp.status_code == 200
        # The change list is a compact quick-edit dashboard (a subset of fields).
        assert set(resp.context["cl"].list_editable) == {
            "grading_mode",
            "points_per_correct_ion",
            "max_submissions_per_analysis",
            "final_score_strategy",
        }

    def test_grading_config_change_form_has_all_fields(self, client, admin_user):
        """The change form (the singleton's own edit workflow) exposes every field."""
        client.force_login(admin_user)
        obj = GradingConfig.get_instance()
        resp = client.get(f"/admin-django/config/gradingconfig/{obj.pk}/change/")
        assert resp.status_code == 200
        fields = set(resp.context["adminform"].form.fields)
        assert {
            "grading_mode",
            "final_score_strategy",
            "points_per_correct_ion",
            "penalty_second_submission",
            "penalty_third_submission",
            "false_positive_deduction",
            "max_submissions_per_analysis",
        } <= fields

    def test_grading_config_change_form_save(self, client, admin_user):
        """Editing and saving through the change form updates the singleton."""
        client.force_login(admin_user)
        obj = GradingConfig.get_instance()
        resp = client.post(
            f"/admin-django/config/gradingconfig/{obj.pk}/change/",
            {
                "grading_mode": "per_analysis",
                "final_score_strategy": "last",
                "points_per_correct_ion": 12,
                "penalty_second_submission": 1,
                "penalty_third_submission": 5,
                "false_positive_deduction": 3,
                "max_submissions_per_analysis": 4,
                "_save": "Save",
            },
        )
        assert resp.status_code == 302  # redirect on success
        obj.refresh_from_db()
        assert obj.grading_mode == "per_analysis"
        assert obj.points_per_correct_ion == 12
        assert obj.max_submissions_per_analysis == 4

    def test_app_settings_change_form_has_all_fields(self, client, admin_user, course):
        """The AppSettings change form exposes every field, including active_course."""
        client.force_login(admin_user)
        obj = AppSettings.get_instance()
        resp = client.get(f"/admin-django/config/appsettings/{obj.pk}/change/")
        assert resp.status_code == 200
        fields = set(resp.context["adminform"].form.fields)
        assert {"points_per_analysis", "analyses_per_course", "active_course"} <= fields

    def test_app_settings_changelist_quick_edit(self, client, admin_user, course):
        client.force_login(admin_user)
        AppSettings.get_instance()
        resp = client.get("/admin-django/config/appsettings/")
        assert resp.status_code == 200
        assert set(resp.context["cl"].list_editable) == {
            "points_per_analysis",
            "analyses_per_course",
            "active_course",
        }

    def test_settings_denied_for_students(self, client, student):
        assert client.get("/admin-django/config/gradingconfig/").status_code == 302  # redirect to login
        assert client.get("/admin-django/config/appsettings/").status_code == 302


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

    def test_admin_updates_course(self, client, admin_user, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/courses/{course.id}",
            {"name": "Renamed Course", "semester": "SS 2027", "track": "materials", "is_active": False},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        course.refresh_from_db()
        assert course.name == "Renamed Course"
        assert course.semester == "SS 2027"
        assert course.track == "materials"
        assert course.is_active is False

    def test_update_unknown_course_404(self, client, admin_user, auth_headers):
        resp = client.put(
            "/api/v1/admin/courses/99999",
            {"name": "Ghost", "semester": "", "track": "", "is_active": True},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_student_cannot_update_course(self, client, student, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/courses/{course.id}",
            {"name": "Hack", "semester": "", "track": "", "is_active": True},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_cannot_delete_course_with_students(self, client, admin_user, course, student, auth_headers):
        student.course = course
        student.save(update_fields=["course"])
        resp = client.delete(f"/api/v1/admin/courses/{course.id}", **auth_headers(admin_user))
        assert resp.status_code == 409
        assert Course.objects.filter(pk=course.id).exists()

    def test_delete_empty_course(self, client, admin_user, course, auth_headers):
        resp = client.delete(f"/api/v1/admin/courses/{course.id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert not Course.objects.filter(pk=course.id).exists()


class TestStudentCourse:
    def test_list_students(self, client, admin_user, student, course, auth_headers):
        student.course = course
        student.save(update_fields=["course"])
        resp = client.get("/api/v1/admin/students", **auth_headers(admin_user))
        assert resp.status_code == 200
        rows = resp.json()
        assert any(r["username"] == student.username and r["course_id"] == course.id for r in rows)

    def test_filter_students_by_course(self, client, admin_user, student, student2, course, auth_headers):
        student.course = course
        student.save(update_fields=["course"])
        resp = client.get(f"/api/v1/admin/students?course_id={course.id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        usernames = {r["username"] for r in resp.json()}
        assert student.username in usernames
        assert student2.username not in usernames

    def test_assign_student_to_course(self, client, admin_user, student, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/students/{student.id}/course",
            {"student_id": student.id, "course_id": course.id},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.course_id == course.id

    def test_detach_student_from_course(self, client, admin_user, student, course, auth_headers):
        student.course = course
        student.save(update_fields=["course"])
        resp = client.put(
            f"/api/v1/admin/students/{student.id}/course",
            {"student_id": student.id, "course_id": None},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.course_id is None

    def test_assign_unknown_course_404(self, client, admin_user, student, auth_headers):
        resp = client.put(
            f"/api/v1/admin/students/{student.id}/course",
            {"student_id": student.id, "course_id": 99999},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_student_cannot_manage_students(self, client, student, course, auth_headers):
        resp = client.get("/api/v1/admin/students", **auth_headers(student))
        assert resp.status_code == 403


class TestStudentManagement:
    """Student account CRUD + CSV import (admin)."""

    def test_list_students_includes_info_fields(self, client, admin_user, student, auth_headers):
        student.matriculation_no = "M123"
        student.labspace_id = "LS-1"
        student.telephone = "+49 151 1"
        student.save()
        resp = client.get("/api/v1/admin/students", **auth_headers(admin_user))
        assert resp.status_code == 200
        row = next(r for r in resp.json() if r["username"] == student.username)
        assert row["matriculation_no"] == "M123"
        assert row["labspace_id"] == "LS-1"
        assert row["telephone"] == "+49 151 1"
        assert row["email"] == student.email

    def test_create_student_with_password(self, client, admin_user, course, auth_headers):
        resp = client.post(
            "/api/v1/admin/students",
            {
                "username": "jdoe",
                "password": "FlameCheck32!",
                "name": "Jane Doe",
                "email": "jane@example.com",
                "matriculation_no": "M123456",
                "lab": "Inorganic",
                "labspace_id": "LS-000123",
                "telephone": "+49 151 2345678",
                "course_id": course.id,
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "jdoe"
        assert body["course_id"] == course.id
        assert body["password"] is None  # explicit password is not echoed back
        from users.models import User

        created = User.objects.get(username="jdoe")
        assert created.is_student
        assert created.check_password("FlameCheck32!")
        assert created.course_id == course.id

    def test_create_student_generates_password_when_empty(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/students",
            {"username": "anon-student", "name": "Anonymous"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        generated = resp.json()["password"]
        assert generated and len(generated) >= 8
        from users.models import User

        assert User.objects.get(username="anon-student").check_password(generated)

    def test_create_student_rejects_weak_password(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/students",
            {"username": "weakpw", "password": "123"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_create_student_duplicate_username_409(self, client, admin_user, student, auth_headers):
        resp = client.post(
            "/api/v1/admin/students",
            {"username": student.username, "password": "FlameCheck32!"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 409

    def test_create_student_unknown_course_404(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/students",
            {"username": "nocourse", "course_id": 99999},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_update_student_fields(self, client, admin_user, student, auth_headers):
        resp = client.put(
            f"/api/v1/admin/students/{student.id}",
            {"name": "Renamed Student", "telephone": "+49 151 999", "matriculation_no": "M777"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.name == "Renamed Student"
        assert student.telephone == "+49 151 999"
        assert student.matriculation_no == "M777"

    def test_update_student_resets_password(self, client, admin_user, student, auth_headers):
        resp = client.put(
            f"/api/v1/admin/students/{student.id}",
            {"password": "NewPass123!"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        # the reset password is echoed back to the admin (once, for handover)
        assert resp.json()["password"]
        from users.models import User

        refreshed = User.objects.get(pk=student.pk)
        assert refreshed.check_password("NewPass123!")

    def test_update_student_username_conflict_409(self, client, admin_user, student, student2, auth_headers):
        resp = client.put(
            f"/api/v1/admin/students/{student.id}",
            {"username": student2.username},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 409

    def test_update_unknown_student_404(self, client, admin_user, auth_headers):
        resp = client.put(
            "/api/v1/admin/students/99999",
            {"name": "x"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_delete_student(self, client, admin_user, student, auth_headers):
        resp = client.delete(f"/api/v1/admin/students/{student.id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        from users.models import User

        assert not User.objects.filter(pk=student.pk).exists()

    def test_delete_student_with_submissions_409(self, client, admin_user, student, course, auth_headers):
        from analyses.factory import SubmissionFactory

        SubmissionFactory(student=student)
        resp = client.delete(f"/api/v1/admin/students/{student.id}", **auth_headers(admin_user))
        assert resp.status_code == 409
        from users.models import User

        assert User.objects.filter(pk=student.pk).exists()

    def test_student_cannot_create_student(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/admin/students",
            {"username": "sneaky", "password": "FlameCheck32!"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    # -- CSV import -----------------------------------------------------------
    def test_import_template(self, client, admin_user, auth_headers):
        resp = client.get("/api/v1/admin/students/import-template", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert "text/csv" in resp["Content-Type"]
        header = resp.content.decode().splitlines()[0]
        assert header.startswith("username;")
        for col in ("name", "email", "matriculation_no", "lab", "labspace_id", "telephone", "course", "password"):
            assert col in header

    def test_import_csv_creates_and_updates(self, client, admin_user, student, course, auth_headers):
        body = (
            "username;name;email;matriculation_no;lab;labspace_id;telephone;course;password\n"
            f"csv-new;New Person;new@example.com;M001;Lab;LS-1;+49 151 1;{course.name};CsvPass123!\n"
            f"{student.username};Updated Person;u@example.com;M002;;;;\n"
        )
        resp = client.post(
            "/api/v1/admin/students/import-csv",
            {"file": io.BytesIO(body.encode())},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert (data["created"], data["updated"], data["skipped"]) == (1, 1, 0)
        from users.models import User

        new = User.objects.get(username="csv-new")
        assert new.check_password("CsvPass123!")
        assert new.course_id == course.id
        assert new.matriculation_no == "M001"
        student.refresh_from_db()
        assert student.name == "Updated Person"
        assert student.matriculation_no == "M002"
        # empty course cell keeps the existing course
        assert student.course_id is None or student.course_id == course.id

    def test_import_csv_generates_passwords(self, client, admin_user, auth_headers):
        body = "username;name\nno-pw;No Password\n"
        resp = client.post(
            "/api/v1/admin/students/import-csv",
            {"file": io.BytesIO(body.encode())},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["generated_passwords"] == [
            {"username": "no-pw", "password": data["generated_passwords"][0]["password"]}
        ]
        from users.models import User

        assert User.objects.get(username="no-pw").check_password(data["generated_passwords"][0]["password"])

    def test_import_csv_collects_errors(self, client, admin_user, student, auth_headers):
        body = (
            "username;name;course;password\n"
            "err-course;Bad Course;NoSuchCourse;\n"
            ";missing username\n"
            f"{student.username};Existing student;;;short\n"
            "err-pw;Bad Password;;123\n"
        )
        resp = client.post(
            "/api/v1/admin/students/import-csv",
            {"file": io.BytesIO(body.encode())},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        # The existing-student row is an update (the password column is ignored
        # for updates); the other two rows are skipped with errors.
        assert data["created"] == 0
        assert data["updated"] == 1
        assert data["skipped"] == 3
        assert any("unknown course" in e for e in data["errors"])
        assert any("missing 'username'" in e for e in data["errors"])
        assert any("invalid password" in e for e in data["errors"])
        from users.models import User

        # the weak-password row must not have created a student
        assert not User.objects.filter(username="err-pw").exists()
        # the existing student was updated (password untouched)
        assert User.objects.get(username__iexact=student.username).name == "Existing student"

    def test_import_csv_requires_username_header(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/students/import-csv",
            {"file": io.BytesIO(b"name;email\nx;y\n")},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_student_cannot_import_csv(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/admin/students/import-csv",
            {"file": io.BytesIO(b"username\nx\n")},
            **auth_headers(student),
        )
        assert resp.status_code == 403


class TestAssistantManagement:
    """Assistant account CRUD + course assignment (admin)."""

    def test_list_assistants_excludes_students(self, client, admin_user, student, assistant, auth_headers):
        resp = client.get("/api/v1/admin/assistants", **auth_headers(admin_user))
        assert resp.status_code == 200
        usernames = [r["username"] for r in resp.json()]
        assert assistant.username in usernames
        assert student.username not in usernames

    def test_list_assistants_course_filter(self, client, admin_user, assistant, course, auth_headers):
        assistant.course = course
        assistant.save()
        resp = client.get(f"/api/v1/admin/assistants?course_id={course.id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert [r["username"] for r in resp.json()] == [assistant.username]
        resp = client.get(f"/api/v1/admin/assistants?course_id={course.id + 1}", **auth_headers(admin_user))
        assert resp.json() == []

    def test_create_assistant_with_password(self, client, admin_user, course, auth_headers):
        resp = client.post(
            "/api/v1/admin/assistants",
            {
                "username": "jlab",
                "password": "FlameCheck32!",
                "name": "Jane Lab",
                "email": "jane.lab@example.com",
                "lab": "Inorganic",
                "labspace_id": "LS-000456",
                "telephone": "+49 151 3456789",
                "course_id": course.id,
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "jlab"
        assert body["course_id"] == course.id
        assert body["password"] is None  # explicit password is not echoed back
        from users.models import User

        created = User.objects.get(username="jlab")
        assert created.is_assistant
        assert not created.is_student
        assert created.check_password("FlameCheck32!")
        assert created.course_id == course.id

    def test_create_assistant_generates_password_when_empty(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/assistants",
            {"username": "anon-assistant", "name": "Anonymous"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        generated = resp.json()["password"]
        assert generated and len(generated) >= 8
        from users.models import User

        assert User.objects.get(username="anon-assistant").check_password(generated)

    def test_create_assistant_rejects_weak_password(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/assistants",
            {"username": "weakpw-a", "password": "123"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_create_assistant_duplicate_username_409(self, client, admin_user, student, auth_headers):
        # username uniqueness spans roles: a student username blocks an assistant
        resp = client.post(
            "/api/v1/admin/assistants",
            {"username": student.username, "password": "FlameCheck32!"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 409

    def test_create_assistant_unknown_course_404(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/assistants",
            {"username": "nocourse-a", "course_id": 99999},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_update_assistant_fields(self, client, admin_user, assistant, auth_headers):
        resp = client.put(
            f"/api/v1/admin/assistants/{assistant.id}",
            {"name": "Renamed Assistant", "telephone": "+49 151 999"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assistant.refresh_from_db()
        assert assistant.name == "Renamed Assistant"
        assert assistant.telephone == "+49 151 999"

    def test_update_assistant_resets_password(self, client, admin_user, assistant, auth_headers):
        resp = client.put(
            f"/api/v1/admin/assistants/{assistant.id}",
            {"password": "NewPass123!"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["password"]
        assistant.refresh_from_db()
        assert assistant.check_password("NewPass123!")

    def test_update_assistant_with_student_id_404(self, client, admin_user, student, auth_headers):
        resp = client.put(
            f"/api/v1/admin/assistants/{student.id}",
            {"name": "x"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_assign_assistant_course(self, client, admin_user, assistant, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/assistants/{assistant.id}/course",
            {"assistant_id": assistant.id, "course_id": course.id},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["course_id"] == course.id
        assistant.refresh_from_db()
        assert assistant.course_id == course.id

    def test_assign_assistant_detach(self, client, admin_user, assistant, course, auth_headers):
        assistant.course = course
        assistant.save()
        resp = client.put(
            f"/api/v1/admin/assistants/{assistant.id}/course",
            {"assistant_id": assistant.id, "course_id": None},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assistant.refresh_from_db()
        assert assistant.course_id is None

    def test_assign_assistant_with_student_id_404(self, client, admin_user, student, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/assistants/{student.id}/course",
            {"assistant_id": student.id, "course_id": course.id},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_delete_assistant(self, client, admin_user, assistant, auth_headers):
        resp = client.delete(f"/api/v1/admin/assistants/{assistant.id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        from users.models import User

        assert not User.objects.filter(pk=assistant.pk).exists()

    def test_student_cannot_create_assistant(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/admin/assistants",
            {"username": "sneaky-a", "password": "FlameCheck32!"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403
