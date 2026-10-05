"""Unit tests for model helpers and the grading logic."""

from datetime import timedelta

import pytest
from config.models import GradingConfig
from django.utils import timezone
from users.models import User

pytestmark = pytest.mark.django_db


class TestGradingLogic:
    def test_per_ion_full_correct(self):
        gc = GradingConfig.get_instance()
        result = gc.score_submission(correct_ion_ids={1, 2, 3}, selected_ion_ids={1, 2, 3}, submission_number=1)
        assert result["score"] == 30
        assert result["correct_count"] == 3
        assert result["wrong_count"] == 0
        assert result["missing_count"] == 0
        assert result["penalty"] == 0
        assert result["ideal_score"] == 30

    def test_per_ion_false_positive(self):
        gc = GradingConfig.get_instance()
        result = gc.score_submission(correct_ion_ids={1, 2}, selected_ion_ids={1, 2, 3}, submission_number=1)
        assert result["correct_count"] == 2
        assert result["wrong_count"] == 1
        assert result["missing_count"] == 0
        assert result["score"] == 20

    def test_per_ion_false_positive_deduction(self):
        gc = GradingConfig.get_instance()
        gc.false_positive_deduction = 2
        result = gc.score_submission(correct_ion_ids={1, 2}, selected_ion_ids={1, 2, 3, 4}, submission_number=1)
        assert result["score"] == 20 - 4  # 2*10 - 2*2

    def test_second_submission_penalty(self):
        gc = GradingConfig.get_instance()
        result = gc.score_submission(correct_ion_ids={1, 2, 3}, selected_ion_ids={1, 2, 3}, submission_number=2)
        assert result["penalty"] == 2
        assert result["score"] == 28

    def test_third_submission_penalty(self):
        gc = GradingConfig.get_instance()
        result = gc.score_submission(correct_ion_ids={1, 2, 3}, selected_ion_ids={1, 2, 3}, submission_number=3)
        assert result["penalty"] == 4
        assert result["score"] == 26

    def test_per_analysis_exact(self):
        gc = GradingConfig.get_instance()
        gc.grading_mode = "per_analysis"
        result = gc.score_submission(correct_ion_ids={1, 2}, selected_ion_ids={1, 2}, submission_number=1)
        assert result["score"] == 10
        assert result["ideal_score"] == 10

    def test_per_analysis_inexact(self):
        gc = GradingConfig.get_instance()
        gc.grading_mode = "per_analysis"
        result = gc.score_submission(correct_ion_ids={1, 2}, selected_ion_ids={1}, submission_number=1)
        assert result["score"] == 0


class TestInstanceHelpers:
    def test_window_status_lifecycle(self, analysis_instance):
        inst = analysis_instance
        assert inst.window_status() == "open"
        inst.window_start = timezone.now() + timedelta(hours=1)
        inst.save()
        assert inst.window_status() == "too_early"
        inst.window_start = timezone.now() - timedelta(hours=2)
        inst.window_end = timezone.now() - timedelta(hours=1)
        inst.save()
        assert inst.window_status() == "too_late"

    def test_score_none_without_submissions(self, assigned_instance):
        assert assigned_instance.score() is None

    def test_score_best_strategy(self, assigned_instance, student, auth_headers):
        from substances.models import Ion

        def submit(symbols, key):
            ids = list(Ion.objects.filter(symbol__in=symbols).values_list("id", flat=True))
            return assigned_instance.submit(student, ids, idempotency_key=key)

        first = submit(["NH4+1"], "k1")
        assert first.score == 10
        second = submit(["NH4+1", "SO4-2", "Cu+2"], "k2")
        assert second.score == 28  # 30 - 2 penalty
        assert assigned_instance.score() == 28  # best

    def test_ideal_score(self, assigned_instance):
        assert assigned_instance.ideal_score() == 30


class TestUserRoles:
    def test_role_properties(self, student, assistant, admin_user):
        assert student.is_student
        assert not student.is_admin
        assert assistant.is_assistant
        assert admin_user.is_admin

    def test_superuser_is_admin_role(self, admin_user):
        assert admin_user.is_superuser
        assert admin_user.role == User.Role.ADMIN
