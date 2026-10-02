"""Tests for the per-course CSV import of analyses (template download + upload)."""

from datetime import datetime, timedelta

import pytest
from analyses.models import AnalysisInstance, AnalysisType
from config.factory import CourseFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from users.factory import StudentAssignmentFactory, UserFactory
from users.models import StudentAssignment

pytestmark = pytest.mark.django_db

TEMPLATE_HEADER = "type,number,window_start,window_end,labspace_ids"


def _upload(client, user, auth_headers, course, text: str, bom: bool = False) -> object:
    """POST ``text`` as a multipart CSV upload to the import endpoint."""
    data = ("\ufeff" + text).encode("utf-8") if bom else text.encode("utf-8")
    # No content_type kwarg: the test client POSTs multipart with its default
    # boundary (an explicit "multipart/form-data" string would lack one).
    return client.post(
        "/api/v1/admin/analysis-instances/import-csv",
        {
            "file": SimpleUploadedFile("import.csv", data, content_type="text/csv"),
            "course_id": str(course.id),
        },
        **auth_headers(user),
    )


class TestTemplateDownload:
    def test_returns_csv_with_header_and_one_row_per_type(
        self, client, admin_user, analysis_type, course, auth_headers
    ):
        other = AnalysisType(name="Zeta panel")
        other.save()
        resp = client.get(
            f"/api/v1/admin/analysis-instances/template-csv?course_id={course.id}",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        assert "attachment" in resp["Content-Disposition"]
        lines = resp.content.decode().strip().splitlines()
        assert lines[0] == TEMPLATE_HEADER
        assert f"{analysis_type.name},1,,," in lines
        assert "Zeta panel,2,,," in lines

    def test_requires_admin(self, client, student, course, auth_headers):
        resp = client.get(
            f"/api/v1/admin/analysis-instances/template-csv?course_id={course.id}",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_unknown_course_404(self, client, admin_user, course, auth_headers):
        resp = client.get(
            "/api/v1/admin/analysis-instances/template-csv?course_id=999999",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404


class TestCsvImport:
    @pytest.fixture
    def course_students(self, course):
        """Two students enrolled in the course with known Labspace IDs."""
        s1 = UserFactory(username="csv-s1", labspace_id="LS-ALPHA", course=course)
        s2 = UserFactory(username="csv-s2", labspace_id="LS-BETA", course=course)
        return s1, s2

    @pytest.fixture
    def other_course_student(self):
        """A student enrolled in a different course (known Labspace ID elsewhere)."""
        return UserFactory(username="csv-elsewhere", labspace_id="LS-OTHER", course=CourseFactory())

    def test_requires_admin(self, client, student, course, auth_headers):
        resp = _upload(client, student, auth_headers, course, TEMPLATE_HEADER + "\n")
        assert resp.status_code == 403

    def test_unknown_course_404(self, client, admin_user, course, auth_headers):
        resp = client.post(
            "/api/v1/admin/analysis-instances/import-csv",
            {
                "file": SimpleUploadedFile("import.csv", b"LS-TEST", content_type="text/csv"),
                "course_id": "999999",
            },
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_creates_instances_and_assigns_by_labspace_id(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        s1, s2 = course_students
        now = timezone.now()
        analysis_type.default_window_start = now
        analysis_type.default_window_end = now + timedelta(days=30)
        analysis_type.save()
        csv_text = (
            TEMPLATE_HEADER + "\n"
            f"{analysis_type.name},1,{now.isoformat()},2026-12-31T23:00:00,LS-ALPHA;LS-BETA\n"
            f"{analysis_type.name},2,,,LS-BETA\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["rows"] == 2
        assert body["analyses_created"] == 2
        assert body["analyses_reused"] == 0
        assert body["students_assigned"] == 3
        assert body["assignments_skipped"] == 0

        first = AnalysisInstance.objects.get(course=course, type=analysis_type, number=1)
        assert first.window_start == now
        assert first.window_end == timezone.make_aware(datetime(2026, 12, 31, 23, 0, 0))
        assert sorted(a.student_id for a in first.assignments.all()) == sorted([s1.id, s2.id])

        second = AnalysisInstance.objects.get(course=course, type=analysis_type, number=2)
        assert list(second.assignments.values_list("student_id", flat=True)) == [s2.id]

    def test_window_falls_back_to_type_default(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        start, end = timezone.now(), timezone.now() + timedelta(days=3)
        analysis_type.default_window_start = start
        analysis_type.default_window_end = end
        analysis_type.save()
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,,,\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        inst = AnalysisInstance.objects.get(course=course, type=analysis_type)
        assert (inst.window_start, inst.window_end) == (start, end)

    def test_reupload_reuses_and_skips(self, client, admin_user, analysis_type, course, course_students, auth_headers):
        analysis_type.default_window_start = timezone.now()
        analysis_type.default_window_end = timezone.now() + timedelta(days=30)
        analysis_type.save()
        csv_text = (
            TEMPLATE_HEADER + "\n"
            f'{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,"LS-ALPHA, LS-BETA"\n'
            f"{analysis_type.name},2,,,LS-BETA\n"
        )
        assert _upload(client, admin_user, auth_headers, course, csv_text).status_code == 200
        assert AnalysisInstance.objects.filter(course=course).count() == 2
        assert StudentAssignment.objects.filter(course=course).count() == 3

        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["analyses_created"] == 0
        assert body["analyses_reused"] == 2
        assert body["students_assigned"] == 0
        assert body["assignments_skipped"] == 3
        assert AnalysisInstance.objects.filter(course=course).count() == 2
        assert StudentAssignment.objects.filter(course=course).count() == 3

    def test_reupload_adds_missing_student(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        s1, s2 = course_students
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,LS-ALPHA\n"
        assert _upload(client, admin_user, auth_headers, course, csv_text).status_code == 200

        csv_text2 = (
            TEMPLATE_HEADER + f'\n{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,"LS-ALPHA, LS-BETA"\n'
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text2)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["analyses_reused"] == 1
        assert body["students_assigned"] == 1
        assert body["assignments_skipped"] == 1
        inst = AnalysisInstance.objects.get(course=course, type=analysis_type)
        assert {a.student_id for a in inst.assignments.all()} == {s1.id, s2.id}

    def test_accepts_bom_prefix(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text, bom=True)
        assert resp.status_code == 200, resp.content

    def test_type_name_case_insensitive(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name.lower()},1,2026-10-01T08:00:00,2026-10-15T18:00:00,\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content

    def test_unknown_type_rejected_atomically(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        csv_text = (
            TEMPLATE_HEADER + "\n"
            f"{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,LS-ALPHA\n"
            "No such type,2,,,LS-BETA\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "unknown analysis type" in str(resp.content.decode())
        assert AnalysisInstance.objects.filter(course=course).count() == 0
        assert StudentAssignment.objects.filter(course=course).count() == 0

    def test_unknown_labspace_id(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,LS-NOPE\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "unknown Labspace ID" in str(resp.content.decode())
        assert StudentAssignment.objects.filter(course=course).count() == 0

    def test_labspace_id_outside_course(
        self, client, admin_user, analysis_type, course, other_course_student, auth_headers
    ):
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,LS-OTHER\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "does not belong to a student in this course" in str(resp.content.decode())

    def test_invalid_number_rejected(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},0,2026-10-01T08:00:00,2026-10-15T18:00:00,\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "'number' must be a positive integer" in str(resp.content.decode())

    def test_invalid_window_rejected(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,not-a-date,2026-10-15T18:00:00,\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "invalid window_start" in str(resp.content.decode())

    def test_window_end_before_start_rejected(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,2026-10-15T18:00:00,2026-10-01T08:00:00,\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "window_end must be after window_start" in str(resp.content.decode())

    def test_missing_default_window_rejected(self, client, admin_user, analysis_type, course, auth_headers):
        analysis_type.default_window_start = None
        analysis_type.default_window_end = None
        analysis_type.save()
        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,,,\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "no default window" in str(resp.content.decode())

    def test_missing_required_column(self, client, admin_user, course, auth_headers):
        resp = _upload(client, admin_user, auth_headers, course, "number,window_start\n1,\n")
        assert resp.status_code == 400
        assert "Missing required column" in str(resp.content.decode())

    def test_empty_file(self, client, admin_user, course, auth_headers):
        resp = _upload(client, admin_user, auth_headers, course, "")
        assert resp.status_code == 400

    def test_header_only_file(self, client, admin_user, course, auth_headers):
        resp = _upload(client, admin_user, auth_headers, course, TEMPLATE_HEADER + "\n")
        assert resp.status_code == 400
        assert "no data rows" in str(resp.content.decode())

    def test_existing_number_conflict_rejected(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        """A student already assigned to a different instance for the same number blocks the row."""
        s1, _ = course_students
        other_type = AnalysisType(name="Conflict panel")
        other_type.save()
        other_instance = AnalysisInstance(
            type=other_type,
            course=course,
            number=1,
            window_start=timezone.now(),
            window_end=timezone.now() + timedelta(days=1),
        )
        other_instance.save()
        StudentAssignmentFactory(course=course, student=s1, instance=other_instance, number=1)

        csv_text = TEMPLATE_HEADER + f"\n{analysis_type.name},1,2026-10-01T08:00:00,2026-10-15T18:00:00,LS-ALPHA\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "already has a different analysis" in str(resp.content.decode())
        # The conflicting instance must not have gained the assignment.
        inst = AnalysisInstance.objects.filter(course=course, type=analysis_type, number=1).first()
        assert inst is None or inst.assignments.count() == 0
