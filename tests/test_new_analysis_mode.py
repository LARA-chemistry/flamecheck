"""
Tests for the "new analysis" submission mode.

A wrong submission (selected set differs from the answer key) hands the student a
fresh, randomly composed analysis of the same type, up to the type's
``max_repetitions``. The newest instance per announcement counts toward the course
total, each earlier attempt subtracts the course's ``retry_point_deduction``, and
the course's assistants are notified.
"""

import uuid

import pytest
from analyses.models import AnalysisInstance, AnalysisNotification, student_course_result
from analyses.services.retry_analysis import maybe_generate_retry
from config.factory import AssistantCourseFactory
from config.models import AssistantCourse, GradingConfig
from substances.models import Ion

pytestmark = pytest.mark.django_db


@pytest.fixture
def assistant_course(assistant, course) -> AssistantCourse:
    """Link the assistant fixture to the course fixture."""
    return AssistantCourseFactory(assistant=assistant, course=course)


def _submit(client, headers, instance, ion_symbols, idem=None):
    ids = list(Ion.objects.filter(symbol__in=ion_symbols).values_list("id", flat=True))
    return client.post(
        f"/api/v1/analyses/{instance.id}/submissions",
        {"ion_ids": ids, "confirmed": True, "idempotency_key": idem or uuid.uuid4().hex},
        content_type="application/json",
        **headers,
    )


def _set_new_analysis_mode(**kwargs) -> GradingConfig:
    """Switch the grading config to the new-analysis mode (plus any overrides)."""
    gc = GradingConfig.get_instance()
    gc.submission_mode = "new_analysis"
    for key, value in kwargs.items():
        setattr(gc, key, value)
    gc.save()
    return gc


class TestRetryGeneration:
    def test_wrong_submission_generates_new_analysis(
        self, client, student, assistant, assistant_course, assigned_instance, grading_config, auth_headers
    ):
        _set_new_analysis_mode()
        resp = _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])  # 1 of 3 -> wrong
        assert resp.status_code == 200
        data = resp.json()
        assert data["retry"]["generated"] is True
        new_inst = AnalysisInstance.objects.get(pk=data["retry"]["new_analysis_id"])
        # Same type, number and course; the window is inherited.
        assert new_inst.type == assigned_instance.type
        assert new_inst.number == assigned_instance.number
        assert new_inst.course == assigned_instance.course
        assert new_inst.window_start == assigned_instance.window_start
        assert new_inst.window_end == assigned_instance.window_end
        # The new answer key is a non-empty subset of the type's possible ions.
        possible = set(assigned_instance.type.possible_ions.all())
        assert set(new_inst.correct_ions.all()).issubset(possible)
        assert new_inst.correct_ions.exists()
        # It is assigned to the student and a notification was raised.
        assert new_inst.assignments.filter(student=student).exists()
        notif = AnalysisNotification.objects.get()
        assert (notif.instance, notif.student, notif.course) == (new_inst, student, assigned_instance.course)

    def test_correct_submission_does_not_generate(
        self, client, student, assigned_instance, grading_config, auth_headers
    ):
        _set_new_analysis_mode()
        resp = _submit(client, auth_headers(student), assigned_instance, ["NH4+1", "SO4-2", "Cu+2"])
        assert resp.status_code == 200
        assert "retry" not in resp.json()
        assert AnalysisInstance.objects.count() == 1
        assert AnalysisNotification.objects.count() == 0

    def test_resubmit_mode_does_not_generate(self, client, student, assigned_instance, grading_config, auth_headers):
        resp = _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])  # default mode
        assert resp.status_code == 200
        assert "retry" not in resp.json()
        assert AnalysisInstance.objects.count() == 1
        assert AnalysisNotification.objects.count() == 0

    def test_max_repetitions_respected(self, client, student, assigned_instance, grading_config, auth_headers):
        _set_new_analysis_mode()
        assigned_instance.type.max_repetitions = 2  # up to 3 instances per announcement
        assigned_instance.type.save()
        current = assigned_instance
        for index in range(3):
            resp = _submit(client, auth_headers(student), current, ["NH4+1"])
            body = resp.json()
            if index < 2:
                assert body["retry"]["generated"] is True
                current = AnalysisInstance.objects.get(pk=body["retry"]["new_analysis_id"])
            else:
                # Third wrong attempt: re-trials exhausted, no new analysis.
                assert "retry" not in body
        assert AnalysisInstance.objects.filter(number=3, assignments__student=student).distinct().count() == 3
        assert AnalysisNotification.objects.count() == 2

    def test_service_returns_none_when_mode_off(self, student, assigned_instance, grading_config):
        submission = assigned_instance.submit(
            student, [assigned_instance.correct_ions.first().id], idempotency_key=uuid.uuid4().hex
        )
        assert maybe_generate_retry(assigned_instance, student, submission) is None


def _set_correct(inst: AnalysisInstance, symbols: list[str]) -> None:
    """Pin an instance's answer key to a known set (like an assistant editing it)."""
    inst.correct_ions.set(list(Ion.objects.filter(symbol__in=symbols).values_list("id", flat=True)))


class TestRetryGrading:
    def test_newest_counts_and_penalty_applied(self, client, student, assigned_instance, grading_config, auth_headers):
        _set_new_analysis_mode(retry_point_deduction=5)
        first = _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])  # 10
        new_inst = AnalysisInstance.objects.get(pk=first.json()["retry"]["new_analysis_id"])
        _set_correct(new_inst, ["NH4+1", "SO4-2", "Cu+2"])
        _submit(client, auth_headers(student), new_inst, ["NH4+1", "SO4-2", "Cu+2"])  # full 30
        result = student_course_result(student, assigned_instance.course)
        # Newest (30) counts; one earlier attempt * 5 penalty.
        assert result["total_score"] == 25
        assert result["ideal_score"] == 30
        assert len(result["instances"]) == 2
        assert result["counting_ids"] == {new_inst.id}

    def test_penalty_floored_at_zero(self, client, student, assigned_instance, grading_config, auth_headers):
        _set_new_analysis_mode(retry_point_deduction=100)
        first = _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])
        new_inst = AnalysisInstance.objects.get(pk=first.json()["retry"]["new_analysis_id"])
        _set_correct(new_inst, ["NH4+1", "SO4-2", "Cu+2"])
        _submit(client, auth_headers(student), new_inst, ["NH4+1"])  # 10 < penalty 100
        result = student_course_result(student, assigned_instance.course)
        assert result["total_score"] == 0

    def test_no_penalty_by_default(self, client, student, assigned_instance, grading_config, auth_headers):
        _set_new_analysis_mode()  # retry_point_deduction stays 0
        first = _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])
        new_inst = AnalysisInstance.objects.get(pk=first.json()["retry"]["new_analysis_id"])
        _set_correct(new_inst, ["NH4+1", "SO4-2", "Cu+2"])
        _submit(client, auth_headers(student), new_inst, ["NH4+1", "SO4-2", "Cu+2"])
        result = student_course_result(student, assigned_instance.course)
        assert result["total_score"] == 30
        assert result["counting_ids"] == {new_inst.id}

    def test_resubmit_mode_unchanged(self, client, student, assigned_instance, grading_config, auth_headers):
        # Default resubmit mode: one instance, best of the submissions counts.
        _submit(client, auth_headers(student), assigned_instance, ["NH4+1", "SO4-2", "Cu+2"])  # 30 first
        _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])  # 10, no penalty
        result = student_course_result(student, assigned_instance.course)
        assert result["total_score"] == 30
        assert result["counting_ids"] == {assigned_instance.id}
        assert len(result["instances"]) == 1


class TestAssistantNotifications:
    def test_assistant_sees_notification(
        self, client, student, assistant, assistant_course, assigned_instance, grading_config, auth_headers
    ):
        _set_new_analysis_mode()
        _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])
        resp = client.get("/api/v1/assistant/notifications", **auth_headers(assistant))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["student"] == student.username
        assert data[0]["course_name"] == assigned_instance.course.name
        assert data[0]["read"] is False

    def test_mark_read(
        self, client, student, assistant, assistant_course, assigned_instance, grading_config, auth_headers
    ):
        _set_new_analysis_mode()
        _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])
        notif_id = AnalysisNotification.objects.get().id
        resp = client.post(f"/api/v1/assistant/notifications/{notif_id}/read", **auth_headers(assistant))
        assert resp.status_code == 200
        data = client.get("/api/v1/assistant/notifications", **auth_headers(assistant)).json()
        assert data[0]["read"] is True

    def test_other_assistant_does_not_see(
        self, client, student, assistant, assistant_course, assigned_instance, grading_config, auth_headers
    ):
        from users.factory import AssistantUserFactory

        _set_new_analysis_mode()
        _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])
        stranger = AssistantUserFactory(username="assistant2")
        data = client.get("/api/v1/assistant/notifications", **auth_headers(stranger)).json()
        assert data == []

    def test_admin_sees_notification(
        self, client, student, admin_user, assigned_instance, grading_config, auth_headers
    ):
        _set_new_analysis_mode()
        _submit(client, auth_headers(student), assigned_instance, ["NH4+1"])
        data = client.get("/api/v1/assistant/notifications", **auth_headers(admin_user)).json()
        assert len(data) == 1


class TestSettingsApi:
    def test_grading_config_exposes_new_fields(self, client, admin_user, grading_config, auth_headers):
        resp = client.get("/api/v1/admin/grading-config", **auth_headers(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["submission_mode"] == "resubmit"
        assert body["retry_point_deduction"] == 0

    def test_update_submission_mode(self, client, admin_user, grading_config, auth_headers):
        payload = {
            "points_per_correct_ion": 10,
            "penalty_second_submission": 2,
            "penalty_third_submission": 4,
            "false_positive_deduction": 0,
            "grading_mode": "per_ion",
            "max_submissions_per_analysis": 3,
            "final_score_strategy": "best",
            "passing_score": 50,
            "submission_mode": "new_analysis",
            "retry_point_deduction": 3,
        }
        resp = client.put(
            "/api/v1/admin/grading-config", payload, content_type="application/json", **auth_headers(admin_user)
        )
        assert resp.status_code == 200
        assert resp.json()["submission_mode"] == "new_analysis"
        assert resp.json()["retry_point_deduction"] == 3

    def test_analysis_type_exposes_max_repetitions(self, client, admin_user, analysis_type, auth_headers):
        resp = client.get("/api/v1/admin/analysis-types", **auth_headers(admin_user))
        assert resp.status_code == 200
        row = next(t for t in resp.json() if t["id"] == analysis_type.id)
        assert row["max_repetitions"] == 2

    def test_update_analysis_type_max_repetitions(self, client, admin_user, analysis_type, auth_headers):
        payload = {
            "name": analysis_type.name,
            "description": analysis_type.description,
            "ion_ids": list(analysis_type.possible_ions.values_list("id", flat=True)),
            "max_repetitions": 5,
        }
        resp = client.put(
            f"/api/v1/admin/analysis-types/{analysis_type.id}",
            payload,
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        analysis_type.refresh_from_db()
        assert analysis_type.max_repetitions == 5
