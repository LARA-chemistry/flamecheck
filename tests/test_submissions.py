"""Tests for the student analysis/submission endpoints and grading logic."""

import uuid
from datetime import timedelta

import pytest
from config.models import GradingConfig
from django.utils import timezone
from substances.models import Ion

pytestmark = pytest.mark.django_db


class TestAnalysisList:
    def test_requires_auth(self, client):
        assert client.get("/api/v1/analyses").status_code == 401

    def test_student_sees_only_own_instances(self, client, student, assistant, assigned_instance, auth_headers):
        resp = client.get("/api/v1/analyses", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == assigned_instance.id
        assert data[0]["window_status"] == "open"

    def test_unassigned_student_sees_nothing(self, client, student, analysis_instance, auth_headers):
        resp = client.get("/api/v1/analyses", **auth_headers(student))
        assert resp.status_code == 200
        assert resp.json() == []


class TestAnalysisDetail:
    def test_hides_correct_ions(self, client, student, assigned_instance, auth_headers):
        resp = client.get(f"/api/v1/analyses/{assigned_instance.id}", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        # the correct set must never appear in the response
        assert "correct" not in data
        cations = [i["symbol"] for i in data["cations"]]
        anions = [i["symbol"] for i in data["anions"]]
        assert "Cu2+" in cations
        assert "Cl-" in anions

    def test_other_student_cannot_access(self, client, assistant, student, assigned_instance, auth_headers):
        resp = client.get(f"/api/v1/analyses/{assigned_instance.id}", **auth_headers(assistant))
        assert resp.status_code == 404


class TestSubmission:
    def _submit(self, client, headers, instance, ion_symbols, idem=None):
        ids = list(Ion.objects.filter(symbol__in=ion_symbols).values_list("id", flat=True))
        return client.post(
            f"/api/v1/analyses/{instance.id}/submissions",
            {
                "ion_ids": ids,
                "confirmed": True,
                "idempotency_key": idem or uuid.uuid4().hex,
            },
            content_type="application/json",
            **headers,
        )

    def test_requires_confirmation(self, client, student, assigned_instance, auth_headers):
        resp = client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": [], "confirmed": False, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code in (400, 422)

    def test_all_correct_scores_full_points(self, client, student, assigned_instance, auth_headers, grading_config):
        resp = self._submit(client, auth_headers(student), assigned_instance, ["NH4+", "SO4-2", "Cu2+"])
        assert resp.status_code == 200
        data = resp.json()
        # 3 correct ions * 10 pts = 30
        assert data["submission"]["score"] == 30
        assert data["result"]["correct_ions"]
        assert data["result"]["wrong_ions"] == []
        assert data["result"]["missing_ions"] == []

    def test_false_positive_and_missing(self, client, student, assigned_instance, auth_headers):
        resp = self._submit(client, auth_headers(student), assigned_instance, ["NH4+", "SO4-2", "Cl-"])
        assert resp.status_code == 200
        data = resp.json()
        sub = data["submission"]
        assert sub["correct_count"] == 2
        assert sub["wrong_count"] == 1
        assert sub["missing_count"] == 1
        assert sub["score"] == 20

    def test_too_early_rejected(self, client, student, assigned_instance, auth_headers):
        assigned_instance.window_start = timezone.now() + timedelta(hours=1)
        assigned_instance.save()
        resp = self._submit(client, auth_headers(student), assigned_instance, ["NH4+"])
        assert resp.status_code in (400, 422)

    def test_too_late_rejected(self, client, student, assigned_instance, auth_headers):
        assigned_instance.window_end = timezone.now() - timedelta(hours=1)
        assigned_instance.save()
        resp = self._submit(client, auth_headers(student), assigned_instance, ["NH4+"])
        assert resp.status_code in (400, 422)

    def test_disallowed_ion_rejected(self, client, student, assigned_instance, auth_headers):
        # Create an ion not in the type's possible set
        other_ion = Ion.objects.create(symbol="I-", name="Iodide", charge=-1, kind="anion", group="Halogens")
        resp = client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": [other_ion.id], "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code in (400, 422)

    def test_idempotency_replay_returns_same_submission(self, client, student, assigned_instance, auth_headers):
        key = uuid.uuid4().hex
        first = self._submit(client, auth_headers(student), assigned_instance, ["NH4+", "SO4-2", "Cu2+"], idem=key)
        second = self._submit(client, auth_headers(student), assigned_instance, ["NH4+", "SO4-2", "Cu2+"], idem=key)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["submission"]["id"] == second.json()["submission"]["id"]
        assert assigned_instance.submissions.count() == 1

    def test_submission_limit_enforced(self, client, student, assigned_instance, auth_headers):
        gc = GradingConfig.get_instance()
        gc.max_submissions_per_analysis = 1
        gc.save()
        assert self._submit(client, auth_headers(student), assigned_instance, ["NH4+"]).status_code == 200
        resp = self._submit(client, auth_headers(student), assigned_instance, ["NH4+", "SO4-2", "Cu2+"])
        assert resp.status_code in (400, 422)

    def test_retry_penalty_applied(self, client, student, assigned_instance, auth_headers):
        first = self._submit(client, auth_headers(student), assigned_instance, ["NH4+"], idem=uuid.uuid4().hex)
        assert first.status_code == 200
        assert first.json()["submission"]["score"] == 10
        second = self._submit(client, auth_headers(student), assigned_instance, ["NH4+", "SO4-2", "Cu2+"])
        assert second.status_code == 200
        sub = second.json()["submission"]
        assert sub["submission_number"] == 2
        # 3*10 - 2 (penalty) = 28
        assert sub["score"] == 28
        assert sub["penalty"] == 2


class TestResultAndSummary:
    def test_result_unavailable_before_submission(self, client, student, assigned_instance, auth_headers):
        resp = client.get(f"/api/v1/analyses/{assigned_instance.id}/result", **auth_headers(student))
        assert resp.status_code == 404

    def test_result_after_submission(self, client, student, assigned_instance, auth_headers):
        ids = list(Ion.objects.filter(symbol__in=["NH4+", "SO4-2", "Cu2+"]).values_list("id", flat=True))
        client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": ids, "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        resp = client.get(f"/api/v1/analyses/{assigned_instance.id}/result", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_score"] == 30
        assert data["ideal_score"] == 30
        assert len(data["submissions"]) == 1

    def test_summary_totals(self, client, student, assigned_instance, auth_headers):
        ids = list(Ion.objects.filter(symbol__in=["NH4+", "SO4-2", "Cu2+"]).values_list("id", flat=True))
        client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": ids, "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        resp = client.get("/api/v1/me/summary", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_score"] == 30
        assert data["ideal_score"] == 30
        assert len(data["analyses"]) == 1


class TestPerAnalysisMode:
    def test_exact_set_scores_full(self, client, student, assigned_instance, auth_headers):
        gc = GradingConfig.get_instance()
        gc.grading_mode = "per_analysis"
        gc.save()
        ids = list(Ion.objects.filter(symbol__in=["NH4+", "SO4-2", "Cu2+"]).values_list("id", flat=True))
        resp = client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": ids, "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 200
        assert resp.json()["submission"]["score"] == 10

    def test_inexact_set_scores_zero(self, client, student, assigned_instance, auth_headers):
        gc = GradingConfig.get_instance()
        gc.grading_mode = "per_analysis"
        gc.save()
        ids = list(Ion.objects.filter(symbol__in=["NH4+", "SO4-2"]).values_list("id", flat=True))
        resp = client.post(
            f"/api/v1/analyses/{assigned_instance.id}/submissions",
            {"ion_ids": ids, "confirmed": True, "idempotency_key": uuid.uuid4().hex},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 200
        assert resp.json()["submission"]["score"] == 0
