"""
Tests for the per-course CSV import of analyses (template download + upload).

The import file uses ``;`` as the column separator and ``,`` as the separator
between the substances (the composition) within a row; each row is one
student's analysis.
"""

from datetime import timedelta

import pytest
from analyses.models import AnalysisInstance, AnalysisType
from config.factory import CourseFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from substances.factory import IonFactory, SubstanceFactory
from users.factory import UserFactory
from users.models import StudentAssignment

pytestmark = pytest.mark.django_db

TEMPLATE_HEADER = "type;number;window_start;window_end;labspace_id;substances"


def _row(name, num, ws="", we="", lab="", sub=""):
    """Build a 6-field CSV row (type;number;window_start;window_end;labspace_id;substances)."""
    return f"{name};{num};{ws};{we};{lab};{sub}"


def _upload(client, user, auth_headers, course, text: str, bom: bool = False) -> object:
    """POST ``text`` as a multipart CSV upload to the import endpoint."""
    data = ("\ufeff" + text).encode("utf-8") if bom else text.encode("utf-8")
    return client.post(
        "/api/v1/admin/analysis-instances/import-csv",
        {
            "file": SimpleUploadedFile("import.csv", data, content_type="text/csv"),
            "course_id": str(course.id),
        },
        **auth_headers(user),
    )


@pytest.fixture
def salts():
    """Salts with distinct ion compositions (for the composition tests)."""
    na = IonFactory.make("sodium")
    cl = IonFactory.make("chloride")
    so4 = IonFactory.make("sulfate")
    br = IonFactory.make("bromide")
    s1 = SubstanceFactory(name="Sodium chloride", formula="NaCl", ions=[na, cl])
    s2 = SubstanceFactory(name="Sodium sulfate", formula="Na2SO4", ions=[na, so4])
    s3 = SubstanceFactory(name="Sodium bromide", formula="NaBr", synonyms=["NaBr (alt)"], ions=[na, br])
    return {
        "sodium_chloride": s1,
        "sodium_sulfate": s2,
        "sodium_bromide": s3,
        "na": na,
        "cl": cl,
        "so4": so4,
        "br": br,
    }


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
        assert _row(analysis_type.name, 1) in lines
        assert _row("Zeta panel", 2) in lines

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
        s1 = UserFactory(username="csv-s1", labspace_id="LS-ALPHA", course=course)
        s2 = UserFactory(username="csv-s2", labspace_id="LS-BETA", course=course)
        return s1, s2

    @pytest.fixture
    def other_course_student(self):
        return UserFactory(username="csv-elsewhere", labspace_id="LS-OTHER", course=CourseFactory())

    def _set_default_window(self, analysis_type):
        analysis_type.default_window_start = timezone.now()
        analysis_type.default_window_end = timezone.now() + timedelta(days=30)
        analysis_type.save()

    def test_requires_admin(self, client, student, course, auth_headers):
        resp = _upload(client, student, auth_headers, course, TEMPLATE_HEADER + "\n")
        assert resp.status_code == 403

    def test_unknown_course_404(self, client, admin_user, course, auth_headers):
        resp = client.post(
            "/api/v1/admin/analysis-instances/import-csv",
            {"file": SimpleUploadedFile("import.csv", b"LS-TEST", content_type="text/csv"), "course_id": "999999"},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_creates_per_student_instance_and_assigns(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        s1, _ = course_students
        self._set_default_window(analysis_type)
        csv_text = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, lab="LS-ALPHA")
            + "\n"
            + _row(analysis_type.name, 1, lab="LS-BETA")
            + "\n"
            + _row(analysis_type.name, 2, lab="LS-BETA")
            + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["rows"] == 3
        assert body["analyses_created"] == 3
        assert body["students_assigned"] == 3
        assert body["assignments_skipped"] == 0
        assert AnalysisInstance.objects.filter(course=course, number=1).count() == 2
        assert AnalysisInstance.objects.filter(course=course, number=2).count() == 1
        alpha_inst = AnalysisInstance.objects.get(course=course, number=1, assignments__student=s1)
        assert list(alpha_inst.assignments.values_list("student_id", flat=True)) == [s1.id]

    def test_window_falls_back_to_type_default(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        start, end = timezone.now(), timezone.now() + timedelta(days=3)
        analysis_type.default_window_start = start
        analysis_type.default_window_end = end
        analysis_type.save()
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-ALPHA") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        inst = AnalysisInstance.objects.get(course=course, number=1)
        assert (inst.window_start, inst.window_end) == (start, end)

    def test_reupload_reuses_and_skips(self, client, admin_user, analysis_type, course, course_students, auth_headers):
        self._set_default_window(analysis_type)
        csv_text = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, "2026-10-01T08:00:00", "2026-10-15T18:00:00", lab="LS-ALPHA")
            + "\n"
            + _row(analysis_type.name, 1, "2026-10-01T08:00:00", "2026-10-15T18:00:00", lab="LS-BETA")
            + "\n"
        )
        assert _upload(client, admin_user, auth_headers, course, csv_text).status_code == 200
        assert AnalysisInstance.objects.filter(course=course).count() == 2
        assert StudentAssignment.objects.filter(course=course).count() == 2

        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["analyses_created"] == 0
        assert body["analyses_reused"] == 2
        assert body["students_assigned"] == 0
        assert body["assignments_skipped"] == 2
        assert AnalysisInstance.objects.filter(course=course).count() == 2

    def test_reupload_adds_missing_student(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        self._set_default_window(analysis_type)
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-ALPHA") + "\n"
        assert _upload(client, admin_user, auth_headers, course, csv_text).status_code == 200

        csv_text2 = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, lab="LS-ALPHA")
            + "\n"
            + _row(analysis_type.name, 1, lab="LS-BETA")
            + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text2)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["analyses_reused"] == 1
        assert body["analyses_created"] == 1
        assert body["students_assigned"] == 1
        assert body["assignments_skipped"] == 1
        assert AnalysisInstance.objects.filter(course=course, number=1).count() == 2

    def test_accepts_bom_prefix(self, client, admin_user, analysis_type, course, course_students, auth_headers):
        self._set_default_window(analysis_type)
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-ALPHA") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text, bom=True)
        assert resp.status_code == 200, resp.content

    def test_type_name_case_insensitive(self, client, admin_user, analysis_type, course, course_students, auth_headers):
        self._set_default_window(analysis_type)
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name.lower(), 1, lab="LS-ALPHA") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content

    def test_unknown_type_rejected_atomically(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        csv_text = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, lab="LS-ALPHA")
            + "\n"
            + _row("No such type", 2, lab="LS-BETA")
            + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "unknown analysis type" in str(resp.content.decode())
        assert AnalysisInstance.objects.filter(course=course).count() == 0

    def test_unknown_labspace_id(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-NOPE") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "unknown Labspace ID" in str(resp.content.decode())
        assert StudentAssignment.objects.filter(course=course).count() == 0

    def test_row_without_labspace_id_creates_unassigned_instance(
        self, client, admin_user, analysis_type, course, auth_headers
    ):
        self._set_default_window(analysis_type)
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1) + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["analyses_created"] == 1
        assert body["students_assigned"] == 0
        inst = AnalysisInstance.objects.get(course=course, number=1)
        assert inst.assignments.count() == 0

    def test_labspace_id_outside_course(
        self, client, admin_user, analysis_type, course, other_course_student, auth_headers
    ):
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-OTHER") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "does not belong to a student in this course" in str(resp.content.decode())

    def test_invalid_number_rejected(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 0, lab="LS-ALPHA") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "'number' must be a positive integer" in str(resp.content.decode())

    def test_invalid_window_rejected(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, "not-a-date", "2026-10-15T18:00:00", lab="LS-ALPHA")
            + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "invalid window_start" in str(resp.content.decode())

    def test_window_end_before_start_rejected(self, client, admin_user, analysis_type, course, auth_headers):
        csv_text = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, "2026-10-15T18:00:00", "2026-10-01T08:00:00", lab="LS-ALPHA")
            + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "window_end must be after window_start" in str(resp.content.decode())

    def test_missing_default_window_rejected(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        analysis_type.default_window_start = None
        analysis_type.default_window_end = None
        analysis_type.save()
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-ALPHA") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "no default window" in str(resp.content.decode())

    def test_missing_required_column(self, client, admin_user, course, auth_headers):
        resp = _upload(client, admin_user, auth_headers, course, "number;window_start\n1;\n")
        assert resp.status_code == 400
        assert "Missing required column" in str(resp.content.decode())

    def test_empty_file(self, client, admin_user, course, auth_headers):
        resp = _upload(client, admin_user, auth_headers, course, "")
        assert resp.status_code == 400

    def test_header_only_file(self, client, admin_user, course, auth_headers):
        resp = _upload(client, admin_user, auth_headers, course, TEMPLATE_HEADER + "\n")
        assert resp.status_code == 400
        assert "no data rows" in str(resp.content.decode())

    def test_skips_blank_lines(self, client, admin_user, analysis_type, course, course_students, auth_headers):
        self._set_default_window(analysis_type)
        csv_text = (
            TEMPLATE_HEADER
            + "\n\n"
            + _row(analysis_type.name, 1, lab="LS-ALPHA")
            + "\n\n"
            + _row(analysis_type.name, 2, lab="LS-ALPHA")
            + "\n\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        assert resp.json()["rows"] == 2


class TestComposition:
    """The composition column becomes the per-student answer key + reference salts."""

    @pytest.fixture
    def course_student(self, course):
        return UserFactory(username="csv-comp", labspace_id="LS-GAMMA", course=course)

    @pytest.fixture
    def course_students(self, course):
        s1 = UserFactory(username="csv-cs1", labspace_id="LS-CS1", course=course)
        s2 = UserFactory(username="csv-cs2", labspace_id="LS-CS2", course=course)
        return s1, s2

    def _set_default_window(self, analysis_type):
        analysis_type.default_window_start = timezone.now()
        analysis_type.default_window_end = timezone.now() + timedelta(days=30)
        analysis_type.save()

    def test_composition_sets_correct_ions_and_substances(
        self, client, admin_user, analysis_type, course, course_student, salts, auth_headers
    ):
        self._set_default_window(analysis_type)
        s1 = salts["sodium_chloride"]
        s2 = salts["sodium_sulfate"]
        csv_text = (
            TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-GAMMA", sub=f"{s1.name},{s2.name}") + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        assert resp.json()["compositions_applied"] == 1
        inst = AnalysisInstance.objects.get(course=course, number=1, assignments__student=course_student)
        assert {i.symbol for i in inst.correct_ions.all()} == {"Na+1", "Cl-1", "SO4-2"}
        assert {s.name for s in inst.assigned_substances.all()} == {s1.name, s2.name}

    def test_composition_matches_by_formula_and_synonym(
        self, client, admin_user, analysis_type, course, course_student, salts, auth_headers
    ):
        self._set_default_window(analysis_type)
        s1 = salts["sodium_chloride"]
        s3 = salts["sodium_bromide"]
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-GAMMA", sub="NaCl,NaBr (alt)") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        inst = AnalysisInstance.objects.get(course=course, number=1, assignments__student=course_student)
        assert {s.name for s in inst.assigned_substances.all()} == {s1.name, s3.name}

    def test_composition_deduplicates_salts(
        self, client, admin_user, analysis_type, course, course_student, salts, auth_headers
    ):
        self._set_default_window(analysis_type)
        s1 = salts["sodium_chloride"]
        csv_text = (
            TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-GAMMA", sub=f"{s1.name},{s1.name}") + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        inst = AnalysisInstance.objects.get(course=course, number=1, assignments__student=course_student)
        assert inst.assigned_substances.count() == 1

    def test_unknown_substance_rejected_atomically(
        self, client, admin_user, analysis_type, course, course_student, salts, auth_headers
    ):
        self._set_default_window(analysis_type)
        csv_text = (
            TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-GAMMA", sub="Potassium permanganate") + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "unknown substance" in str(resp.content.decode())
        assert AnalysisInstance.objects.filter(course=course).count() == 0

    def test_per_student_compositions_differ(self, client, admin_user, analysis_type, course, salts, auth_headers):
        a = UserFactory(username="csv-pa", labspace_id="LS-PA", course=course)
        b = UserFactory(username="csv-pb", labspace_id="LS-PB", course=course)
        self._set_default_window(analysis_type)
        s1 = salts["sodium_chloride"]
        s2 = salts["sodium_sulfate"]
        csv_text = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, lab="LS-PA", sub=s1.name)
            + "\n"
            + _row(analysis_type.name, 1, lab="LS-PB", sub=s2.name)
            + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        assert resp.json()["compositions_applied"] == 2
        inst_a = AnalysisInstance.objects.get(course=course, number=1, assignments__student=a)
        inst_b = AnalysisInstance.objects.get(course=course, number=1, assignments__student=b)
        assert {i.symbol for i in inst_a.correct_ions.all()} == {"Na+1", "Cl-1"}
        assert {i.symbol for i in inst_b.correct_ions.all()} == {"Na+1", "SO4-2"}

    def test_existing_assignment_conflict_rejected(
        self, client, admin_user, analysis_type, course, course_students, auth_headers
    ):
        s1, _ = course_students
        other_type = AnalysisType(name="Conflict panel")
        other_type.save()
        other_instance = AnalysisInstance.objects.create(
            type=other_type,
            course=course,
            number=1,
            window_start=timezone.now(),
            window_end=timezone.now() + timedelta(days=1),
        )
        StudentAssignment.objects.create(course=course, student=s1, instance=other_instance, number=1)
        csv_text = (
            TEMPLATE_HEADER
            + "\n"
            + _row(analysis_type.name, 1, "2026-10-01T08:00:00", "2026-10-15T18:00:00", lab="LS-CS1")
            + "\n"
        )
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 400
        assert "already has a different analysis" in str(resp.content.decode())

    def test_empty_composition_leaves_ions_untouched(
        self, client, admin_user, analysis_type, course, course_student, salts, auth_headers
    ):
        self._set_default_window(analysis_type)
        inst = AnalysisInstance.objects.create(
            type=analysis_type,
            course=course,
            number=1,
            window_start=timezone.now(),
            window_end=timezone.now() + timedelta(days=30),
        )
        inst.correct_ions.set([salts["cl"].id, salts["so4"].id])
        StudentAssignment.objects.create(course=course, student=course_student, instance=inst, number=1)
        csv_text = TEMPLATE_HEADER + "\n" + _row(analysis_type.name, 1, lab="LS-GAMMA") + "\n"
        resp = _upload(client, admin_user, auth_headers, course, csv_text)
        assert resp.status_code == 200, resp.content
        assert resp.json()["compositions_applied"] == 0
        assert resp.json()["analyses_reused"] == 1
        assert {i.symbol for i in inst.correct_ions.all()} == {"Cl-1", "SO4-2"}
