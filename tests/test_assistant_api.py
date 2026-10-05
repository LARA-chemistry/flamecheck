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

        ids = list(Ion.objects.filter(symbol__in=["NH4+1", "SO4-2", "Cu+2"]).values_list("id", flat=True))
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
        assert any(i["symbol"] == "Cu+2" for i in data[0]["correct_ions"])


class TestCsvExport:
    def test_export_returns_csv(
        self, client, assistant, assistant_course, course, student, assigned_instance, auth_headers
    ):
        student.course = course
        student.save()
        import uuid

        from substances.models import Ion

        ids = list(Ion.objects.filter(symbol__in=["NH4+1", "SO4-2", "Cu+2"]).values_list("id", flat=True))
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


class TestSubstanceOverview:
    def test_requires_assistant_role(self, client, student, assistant_course, course, auth_headers):
        resp = client.get(f"/api/v1/assistant/courses/{course.id}/substance-overview", **auth_headers(student))
        assert resp.status_code == 403

    def test_invisible_course_404(self, client, assistant, assistant_course, auth_headers):
        other = CourseFactory(name="Other Course", is_active=True)
        resp = client.get(f"/api/v1/assistant/courses/{other.id}/substance-overview", **auth_headers(assistant))
        assert resp.status_code == 404

    def test_overview_lists_substances_of_correct_ions(
        self, client, assistant, assistant_course, course, student, assigned_instance, auth_headers
    ):
        from substances.factory import IonFactory, SubstanceFactory
        from substances.models import Ion

        # The assigned instance's correct set is NH4+, SO4-2, Cu2+.
        sulfate = IonFactory.make("sulfate")
        relevant = SubstanceFactory(name="Copper sulfate", formula="CuSO4")
        relevant.ions.add(sulfate)
        unrelated_ion = IonFactory(symbol="Unrelated9", name="Unrelated", kind=Ion.Kind.ANION)
        unrelated = SubstanceFactory(name="Unrelated salt", formula="UX9")
        unrelated.ions.add(unrelated_ion)

        resp = client.get(f"/api/v1/assistant/courses/{course.id}/substance-overview", **auth_headers(assistant))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["analyses"]) == 1
        analysis = data["analyses"][0]
        assert {i["symbol"] for i in analysis["correct_ions"]} == {"NH4+1", "SO4-2", "Cu+2"}
        assert analysis["student_count"] == 1
        assert analysis["sample_count"] == 1  # default: one sample per assigned student
        assert [s["name"] for s in analysis["substances"]] == ["Copper sulfate"]
        assert data["totals"] == [
            {
                "id": relevant.id,
                "name": "Copper sulfate",
                "formula": "CuSO4",
                "count": 1,
                "used_in_analyses": 1,
            }
        ]
        assert data["total_units"] == 1
        assert data["distinct_substances"] == 1

    def test_samples_per_analysis_override(
        self, client, assistant, assistant_course, course, student, assigned_instance, auth_headers
    ):
        from substances.factory import IonFactory, SubstanceFactory

        relevant = SubstanceFactory(name="Copper sulfate", formula="CuSO4")
        relevant.ions.add(IonFactory.make("sulfate"))

        resp = client.get(
            f"/api/v1/assistant/courses/{course.id}/substance-overview?samples_per_analysis=5",
            **auth_headers(assistant),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["samples_per_analysis"] == 5
        assert data["analyses"][0]["sample_count"] == 5
        assert data["totals"][0]["count"] == 5
        assert data["total_units"] == 5


class TestMCResults:
    """Multiple-choice results in the assistant students overview."""

    @pytest.fixture
    def mc_sheet(self, db, course, student):
        """An open single-question MC sheet assigned to the student fixture."""
        from multichoice.factory import MCCardFactory, MCQuestionFactory, MCSheetFactory, MCStudentAssignmentFactory

        question = MCQuestionFactory(course=course)
        card = MCCardFactory(course=course, questions=[question], title="EP Monograph")
        sheet = MCSheetFactory(card=card, course=course, number=1)
        MCStudentAssignmentFactory(course=course, sheet=sheet, student=student, number=1)
        return sheet

    def _submit(self, sheet, student, *, correct: bool = True, key: str) -> None:
        """Submit one answer for the sheet (the correct option, or a wrong one)."""
        q = sheet.questions()[0]
        option = q.correct_option() if correct else next(o for o in q.options() if not o.is_correct)
        sheet.submit(student, {q.id: option.id}, idempotency_key=key)

    def test_roster_carries_submitted_mc(
        self, client, assistant, assistant_course, course, student, mc_sheet, auth_headers, idempotency_key
    ):
        student.course = course
        student.save()
        self._submit(mc_sheet, student, correct=True, key=idempotency_key)

        resp = client.get(f"/api/v1/assistant/courses/{course.id}", **auth_headers(assistant))
        assert resp.status_code == 200
        entry = next(s for s in resp.json()["students"] if s["username"] == student.username)
        assert len(entry["mc"]) == 1
        assert entry["mc"][0]["card"] == "EP Monograph"
        assert entry["mc"][0]["window_status"] == "submitted"
        assert entry["mc"][0]["submission_count"] == 1
        assert entry["mc"][0]["score"] == 10
        assert entry["mc"][0]["ideal_score"] == 10

    def test_roster_pending_mc_has_no_score(
        self, client, assistant, assistant_course, course, student, mc_sheet, auth_headers
    ):
        student.course = course
        student.save()

        resp = client.get(f"/api/v1/assistant/courses/{course.id}", **auth_headers(assistant))
        assert resp.status_code == 200
        entry = next(s for s in resp.json()["students"] if s["username"] == student.username)
        assert entry["mc"][0]["window_status"] == "open"
        assert entry["mc"][0]["submission_count"] == 0
        assert entry["mc"][0]["score"] is None

    def test_student_mc_submissions_detail(
        self, client, assistant, assistant_course, course, student, mc_sheet, auth_headers, idempotency_key
    ):
        student.course = course
        student.save()
        self._submit(mc_sheet, student, correct=False, key=idempotency_key)

        resp = client.get(f"/api/v1/assistant/students/{student.id}/mc-submissions", **auth_headers(assistant))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["card"] == "EP Monograph"
        assert entry["window_status"] == "submitted"
        assert entry["score"] == 8  # 10 points - 2 penalty for the one wrong answer
        # the correct answer key is revealed
        assert len(entry["questions"]) == 1
        assert entry["questions"][0]["correct_option_id"] is not None
        assert any(o["is_correct"] for o in entry["questions"][0]["options"])
        # the submission carries the per-question breakdown
        assert len(entry["submissions"]) == 1
        per = entry["submissions"][0]["per_question"]
        assert len(per) == 1
        assert per[0]["is_correct"] is False
        assert per[0]["selected_option_id"] is not None

    def test_mc_submissions_requires_assistant(self, client, student, assistant_course, course, mc_sheet, auth_headers):
        student.course = course
        student.save()
        resp = client.get(f"/api/v1/assistant/students/{student.id}/mc-submissions", **auth_headers(student))
        assert resp.status_code == 403

    def test_mc_submissions_requires_auth(self, client, student, assistant_course, course, mc_sheet):
        resp = client.get(f"/api/v1/assistant/students/{student.id}/mc-submissions")
        assert resp.status_code == 401

    def test_mc_submissions_invisible_student_404(
        self, client, assistant, assistant_course, course, student2, auth_headers
    ):
        other = CourseFactory(name="Other Course", is_active=True)
        student2.course = other
        student2.save()
        resp = client.get(f"/api/v1/assistant/students/{student2.id}/mc-submissions", **auth_headers(assistant))
        assert resp.status_code == 404
