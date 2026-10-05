"""Tests for the multiple-choice admin + student APIs."""

from __future__ import annotations

from datetime import timedelta

import pytest
from config.models import GradingConfig
from multichoice.factory import (
    MCCardFactory,
    MCQuestionFactory,
    MCSheetFactory,
    MCStudentAssignmentFactory,
)
from multichoice.models import MCSheet
from users.factory import UserFactory
from users.models import User

pytestmark = pytest.mark.django_db


def _now():
    from django.utils import timezone

    return timezone.now()


def _open_window() -> tuple[str, str]:
    now = _now()
    return (now - timedelta(hours=1)).isoformat(), (now + timedelta(hours=1)).isoformat()


def _late_window() -> tuple[str, str]:
    now = _now()
    return (now - timedelta(hours=2)).isoformat(), (now - timedelta(hours=1)).isoformat()


class TestAdminAuth:
    def test_requires_admin(self, client, student, auth_headers):
        resp = client.get("/api/v1/admin/multichoice/questions", **auth_headers(student))
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        assert client.get("/api/v1/admin/multichoice/questions").status_code == 401


class TestQuestionAdmin:
    def test_create_question(self, client, admin_user, course, auth_headers):
        resp = client.post(
            f"/api/v1/admin/multichoice/questions?course_id={course.id}",
            {
                "text": "Which flame colour for Na?",
                "description": "Flame test",
                "remarks": "lab 1",
                "options": [
                    {"text": "Yellow", "is_correct": True, "sort_order": 0},
                    {"text": "Violet", "is_correct": False, "sort_order": 1},
                ],
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["text"] == "Which flame colour for Na?"
        assert len(body["options"]) == 2
        assert any(o["is_correct"] for o in body["options"])

    def test_create_requires_exactly_one_correct(self, client, admin_user, course, auth_headers):
        resp = client.post(
            f"/api/v1/admin/multichoice/questions?course_id={course.id}",
            {
                "text": "Q?",
                "options": [
                    {"text": "A", "is_correct": False},
                    {"text": "B", "is_correct": False},
                ],
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_create_requires_two_options(self, client, admin_user, course, auth_headers):
        resp = client.post(
            f"/api/v1/admin/multichoice/questions?course_id={course.id}",
            {"text": "Q?", "options": [{"text": "Only", "is_correct": True}]},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_update_text_always(self, client, admin_user, course, auth_headers):
        q = MCQuestionFactory(course=course)
        resp = client.put(
            f"/api/v1/admin/multichoice/questions/{q.id}",
            {"text": "Changed?", "options": None},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Changed?"

    def test_update_options_rejected_when_in_use(self, client, admin_user, course, auth_headers):
        q = MCQuestionFactory(course=course)
        card = MCCardFactory(course=course, questions=[q])
        sheet = MCSheetFactory(card=card, course=course)
        student = UserFactory()
        MCStudentAssignmentFactory(sheet=sheet, student=student, course=course)
        sheet.submit(student, {q.id: q.correct_option().id}, idempotency_key="k")
        resp = client.put(
            f"/api/v1/admin/multichoice/questions/{q.id}",
            {
                "text": "Q?",
                "options": [
                    {"text": "NewA", "is_correct": True},
                    {"text": "NewB", "is_correct": False},
                ],
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 409

    def test_delete_used_question_rejected(self, client, admin_user, course, auth_headers):
        q = MCQuestionFactory(course=course)
        MCCardFactory(course=course, questions=[q])
        url = f"/api/v1/admin/multichoice/questions/{q.id}"
        assert client.delete(url, **auth_headers(admin_user)).status_code == 409


class TestCardAdmin:
    def _two_questions(self, course) -> list:
        return [MCQuestionFactory(course=course), MCQuestionFactory(course=course)]

    def test_create_card(self, client, admin_user, course, auth_headers):
        qs = self._two_questions(course)
        resp = client.post(
            f"/api/v1/admin/multichoice/cards?course_id={course.id}",
            {"title": "Card A", "description": "", "remarks": "", "question_ids": [qs[0].id, qs[1].id]},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["title"] == "Card A"
        assert len(body["questions"]) == 2

    def test_create_card_rejects_four_questions(self, client, admin_user, course, auth_headers):
        qs = [MCQuestionFactory(course=course) for _ in range(4)]
        resp = client.post(
            f"/api/v1/admin/multichoice/cards?course_id={course.id}",
            {"title": "Too many", "question_ids": [q.id for q in qs]},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_create_card_rejects_foreign_course_question(self, client, admin_user, course, auth_headers):
        other = MCQuestionFactory()  # different course
        resp = client.post(
            f"/api/v1/admin/multichoice/cards?course_id={course.id}",
            {"title": "X", "question_ids": [other.id]},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_update_card_questions_rejected_when_sheets_exist(self, client, admin_user, course, auth_headers):
        qs = self._two_questions(course)
        card = MCCardFactory(course=course, questions=qs)
        MCSheetFactory(card=card, course=course)
        resp = client.put(
            f"/api/v1/admin/multichoice/cards/{card.id}",
            {"title": "Card A", "question_ids": [qs[0].id]},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 409


class TestSheetAdmin:
    def test_create_sheet(self, client, admin_user, course, auth_headers):
        card = MCCardFactory(course=course)
        student = UserFactory(course=course)
        start, end = _open_window()
        resp = client.post(
            "/api/v1/admin/multichoice/sheets",
            {
                "card_id": card.id,
                "course_id": course.id,
                "window_start": start,
                "window_end": end,
                "number": 1,
                "student_ids": [student.id],
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["student_ids"] == [student.id]
        assert body["card_title"] == card.title

    def test_create_sheet_requires_valid_window(self, client, admin_user, course, auth_headers):
        card = MCCardFactory(course=course)
        now = _now()
        resp = client.post(
            "/api/v1/admin/multichoice/sheets",
            {
                "card_id": card.id,
                "course_id": course.id,
                "window_start": (now + timedelta(hours=1)).isoformat(),
                "window_end": (now - timedelta(hours=1)).isoformat(),
                "student_ids": [],
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422


class TestStudentEndpoints:
    def _setup_sheet(self, course, window: tuple[str, str] | None = None) -> tuple[MCSheet, User]:
        card = MCCardFactory(course=course)
        start, end = window or _open_window()
        from datetime import datetime

        sheet = MCSheetFactory(
            card=card, course=course, window_start=datetime.fromisoformat(start), window_end=datetime.fromisoformat(end)
        )
        student = UserFactory(course=course)
        MCStudentAssignmentFactory(sheet=sheet, student=student, course=course)
        return sheet, student

    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/mc-sheets").status_code == 401

    def test_list_shows_own_sheets(self, client, course, auth_headers):
        sheet, student = self._setup_sheet(course)
        resp = client.get("/api/v1/mc-sheets", **auth_headers(student))
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == sheet.id
        assert body[0]["window_status"] == "open"

    def test_detail_hides_correct_before_submission(self, client, course, auth_headers):
        sheet, student = self._setup_sheet(course)
        resp = client.get(f"/api/v1/mc-sheets/{sheet.id}", **auth_headers(student))
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] is None
        for q in body["questions"]:
            assert "is_correct" not in q["options"][0]

    def test_cannot_access_others_sheet(self, client, course, auth_headers):
        sheet, _ = self._setup_sheet(course)
        other = UserFactory(course=course)
        assert client.get(f"/api/v1/mc-sheets/{sheet.id}", **auth_headers(other)).status_code == 404

    def test_submit_and_grade(self, client, course, auth_headers):
        sheet, student = self._setup_sheet(course)
        answers = {str(q.id): q.correct_option().id for q in sheet.questions()}
        resp = client.post(
            f"/api/v1/mc-sheets/{sheet.id}/submissions",
            {"answers": answers, "idempotency_key": "k1"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["score"] == 10
        assert body["correct_count"] == len(sheet.questions())

    def test_submit_idempotent(self, client, course, auth_headers):
        sheet, student = self._setup_sheet(course)
        answers = {str(q.id): q.correct_option().id for q in sheet.questions()}
        key = "same-key"
        first = client.post(
            f"/api/v1/mc-sheets/{sheet.id}/submissions",
            {"answers": answers, "idempotency_key": key},
            content_type="application/json",
            **auth_headers(student),
        )
        second = client.post(
            f"/api/v1/mc-sheets/{sheet.id}/submissions",
            {"answers": answers, "idempotency_key": key},
            content_type="application/json",
            **auth_headers(student),
        )
        assert first.json()["id"] == second.json()["id"]
        assert sheet.submissions.count() == 1

    def test_submit_rejected_when_window_closed(self, client, course, auth_headers):
        sheet, student = self._setup_sheet(course, _late_window())
        answers = {str(q.id): q.correct_option().id for q in sheet.questions()}
        resp = client.post(
            f"/api/v1/mc-sheets/{sheet.id}/submissions",
            {"answers": answers, "idempotency_key": "k"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 422

    def test_result_shows_correct_after_submission(self, client, course, auth_headers):
        sheet, student = self._setup_sheet(course)
        answers = {str(q.id): q.correct_option().id for q in sheet.questions()}
        client.post(
            f"/api/v1/mc-sheets/{sheet.id}/submissions",
            {"answers": answers, "idempotency_key": "k"},
            content_type="application/json",
            **auth_headers(student),
        )
        resp = client.get(f"/api/v1/mc-sheets/{sheet.id}/result", **auth_headers(student))
        assert resp.status_code == 200
        body = resp.json()
        assert body["score"] == 10
        assert all(pq["is_correct"] for pq in body["per_question"])

    def test_wrong_answer_penalised(self, client, course, auth_headers):
        course2 = course
        from multichoice.factory import MCCardFactory as C

        questions = [MCQuestionFactory(course=course2) for _ in range(3)]
        card = C(course=course2, questions=questions)
        sheet = MCSheetFactory(card=card, course=course2)
        gc = GradingConfig.get_for_course(course2)
        gc.mc_points_per_card = 10
        gc.mc_penalty_per_wrong = 2
        gc.save()
        student = UserFactory(course=course2)
        MCStudentAssignmentFactory(sheet=sheet, student=student, course=course2)
        answers = {str(q.id): q.correct_option().id for q in questions}
        answers[str(questions[0].id)] = questions[0].options_set.filter(is_correct=False).first().id
        resp = client.post(
            f"/api/v1/mc-sheets/{sheet.id}/submissions",
            {"answers": answers, "idempotency_key": "k"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == 8


class TestPerCourseGradingConfig:
    def test_mc_fields_in_grading_config_payload(self, client, admin_user, course, auth_headers):
        resp = client.put(
            f"/api/v1/admin/courses/{course.id}/grading-config",
            {
                "points_per_correct_ion": 10,
                "penalty_second_submission": 2,
                "penalty_third_submission": 4,
                "false_positive_deduction": 0,
                "grading_mode": "per_ion",
                "max_submissions_per_analysis": 3,
                "final_score_strategy": "best",
                "passing_score": 50,
                "submission_mode": "resubmit",
                "retry_point_deduction": 0,
                "mc_points_per_card": 20,
                "mc_penalty_per_wrong": 5,
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["mc_points_per_card"] == 20
        assert body["mc_penalty_per_wrong"] == 5
        gc = GradingConfig.get_for_course(course)
        assert gc.mc_points_per_card == 20
        assert gc.mc_penalty_per_wrong == 5
