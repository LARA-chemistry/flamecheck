"""Tests for the assistant endpoints (roster, detail, stats, CSV export)."""

import pytest
from config.factory import AssistantCourseFactory, CourseFactory
from config.models import AssistantCourse

pytestmark = pytest.mark.django_db


@pytest.fixture
def assistant_course(assistant, course) -> AssistantCourse:
    """Link the assistant fixture to the course fixture (via factory)."""
    return AssistantCourseFactory(assistant=assistant, course=course)


class TestCourseVisibility:
    def test_requires_auth(self, client):
        assert client.get("/api/v1/assistant/courses").status_code == 401

    def test_student_cannot_access(self, client, student, assistant_course, auth_headers):
        resp = client.get("/api/v1/assistant/courses", **auth_headers(student))
        assert resp.status_code == 403

    def test_assistant_sees_assigned_course(self, client, assistant, assistant_course, course, auth_headers):
        resp = client.get("/api/v1/assistant/courses", **auth_headers(assistant))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == course.name

    def test_assistant_does_not_see_other_courses(self, client, assistant, assistant_course, auth_headers):
        other = CourseFactory(name="Other Course", is_active=True)
        resp = client.get("/api/v1/assistant/courses", **auth_headers(assistant))
        names = {c["name"] for c in resp.json()}
        assert other.name not in names

    def test_admin_sees_all_active_courses(self, client, admin_user, assistant_course, auth_headers):
        other = CourseFactory(name="Other Course", is_active=True)
        resp = client.get("/api/v1/assistant/courses", **auth_headers(admin_user))
        names = {c["name"] for c in resp.json()}
        assert other.name in names


class TestRoster:
    def test_roster_contains_students_with_barcode(
        self, client, assistant, assistant_course, course, student, student_barcode, assigned_instance, auth_headers
    ):
        student.course = course
        student.save()
        resp = client.get(f"/api/v1/assistant/courses/{course.id}", **auth_headers(assistant))
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_assignments"] == 1
        assert data["stats"]["submitted"] == 0
        entry = next(s for s in data["students"] if s["username"] == student.username)
        assert entry["barcode"] == student_barcode.value
        assert len(entry["analyses"]) == 1

    def test_student_submissions_detail(
        self, client, assistant, assistant_course, course, student, assigned_instance, auth_headers
    ):
        student.course = course
        student.save()
        import uuid

        from substances.models import Ion

        ids = list(Ion.objects.filter(symbol__in=["NH4+", "SO4-2", "Cu2+"]).values_list("id", flat=True))
        client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": ids, "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        resp = client.get(f"/api/v1/assistant/students/{student.id}/submissions", **auth_headers(assistant))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert len(data[0]["submissions"]) == 1
        # assistant can see the correct answer key
        assert any(i["symbol"] == "Cu2+" for i in data[0]["correct_ions"])


class TestCsvExport:
    def test_export_returns_csv(
        self, client, assistant, assistant_course, course, student, assigned_instance, auth_headers
    ):
        student.course = course
        student.save()
        import uuid

        from substances.models import Ion

        ids = list(Ion.objects.filter(symbol__in=["NH4+", "SO4-2", "Cu2+"]).values_list("id", flat=True))
        client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": ids, "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        resp = client.get(f"/api/v1/assistant/courses/{course.id}/export/csv", **auth_headers(assistant))
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        body = resp.content.decode()
        assert "student_username" in body.splitlines()[0]
        assert student.username in body
