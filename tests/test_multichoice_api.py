"""Tests for the multiple-choice admin + student APIs."""

from __future__ import annotations

from datetime import timedelta

import pytest
from config.factory import AssistantCourseFactory
from config.models import AssistantCourse, GradingConfig
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

    def test_card_payload_includes_course(self, client, admin_user, course, auth_headers):
        card = MCCardFactory(course=course)
        resp = client.get("/api/v1/admin/multichoice/cards", **auth_headers(admin_user))
        assert resp.status_code == 200
        entry = next(c for c in resp.json() if c["id"] == card.id)
        assert entry["course_id"] == course.id
        assert entry["course_name"] == course.name

    def test_question_payload_includes_course(self, client, admin_user, course, auth_headers):
        q = MCQuestionFactory(course=course)
        resp = client.get("/api/v1/admin/multichoice/questions", **auth_headers(admin_user))
        assert resp.status_code == 200
        entry = next(item for item in resp.json() if item["id"] == q.id)
        assert entry["course_id"] == course.id
        assert entry["course_name"] == course.name

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

    def test_list_sheets_filtered_by_card(self, client, admin_user, course, auth_headers):
        card_a = MCCardFactory(course=course)
        card_b = MCCardFactory(course=course)
        sheet_a = MCSheetFactory(card=card_a, course=course)
        sheet_b = MCSheetFactory(card=card_b, course=course)
        resp = client.get(f"/api/v1/admin/multichoice/sheets?card_id={card_a.id}", **auth_headers(admin_user))
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert ids == {sheet_a.id}
        assert sheet_b.id not in ids

    def test_delete_sheet_with_submissions_rejected(self, client, admin_user, course, auth_headers):
        sheet = MCSheetFactory(course=course)
        student = UserFactory(course=course)
        MCStudentAssignmentFactory(sheet=sheet, student=student, course=course)
        answers = {q.id: q.correct_option().id for q in sheet.questions()}
        sheet.submit(student, answers, idempotency_key="k-delete")
        resp = client.delete(f"/api/v1/admin/multichoice/sheets/{sheet.id}", **auth_headers(admin_user))
        assert resp.status_code == 409


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

    def test_shared_sheet_status_is_per_student(self, client, course, auth_headers):
        # Two students on one sheet: the non-submitter still sees the sheet as
        # open with no score/result, while the submitter sees the graded result.
        sheet, student = self._setup_sheet(course)
        other = UserFactory(course=course)
        MCStudentAssignmentFactory(sheet=sheet, student=other, course=course)
        answers = {str(q.id): q.correct_option().id for q in sheet.questions()}
        resp = client.post(
            f"/api/v1/mc-sheets/{sheet.id}/submissions",
            {"answers": answers, "idempotency_key": "k-shared"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 200

        body = client.get("/api/v1/mc-sheets", **auth_headers(other)).json()
        assert body[0]["window_status"] == "open"
        assert body[0]["score"] is None
        assert body[0]["submission_count"] == 0

        detail = client.get(f"/api/v1/mc-sheets/{sheet.id}", **auth_headers(other)).json()
        assert detail["window_status"] == "open"
        assert detail["result"] is None

        mine = client.get(f"/api/v1/mc-sheets/{sheet.id}", **auth_headers(student)).json()
        assert mine["window_status"] == "submitted"
        assert mine["result"]["score"] == 10


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

    @pytest.fixture
    def assistant_course(self, assistant, course) -> AssistantCourse:
        """Link the assistant fixture to the course fixture."""
        return AssistantCourseFactory(assistant=assistant, course=course)

    def test_assistant_updates_own_course_grading_config(
        self, client, assistant, assistant_course, course, auth_headers
    ):
        resp = client.get(f"/api/v1/admin/courses/{course.id}/grading-config", **auth_headers(assistant))
        assert resp.status_code == 200
        payload = {**resp.json(), "mc_points_per_card": 15, "mc_penalty_per_wrong": 3}
        resp = client.put(
            f"/api/v1/admin/courses/{course.id}/grading-config",
            payload,
            content_type="application/json",
            **auth_headers(assistant),
        )
        assert resp.status_code == 200, resp.content
        gc = GradingConfig.get_for_course(course)
        assert gc.mc_points_per_card == 15
        assert gc.mc_penalty_per_wrong == 3

    def test_assistant_cannot_update_other_course_grading_config(
        self, client, assistant, assistant_course, course, auth_headers
    ):
        other = MCQuestionFactory().course  # a course the assistant does not support
        resp = client.get(f"/api/v1/admin/courses/{course.id}/grading-config", **auth_headers(assistant))
        payload = {**resp.json(), "mc_points_per_card": 1}
        resp = client.put(
            f"/api/v1/admin/courses/{other.id}/grading-config",
            payload,
            content_type="application/json",
            **auth_headers(assistant),
        )
        assert resp.status_code == 404


class TestAssistantAccess:
    """Assistants manage MC content for the courses they support (and only those)."""

    @pytest.fixture
    def assistant_course(self, assistant, course) -> AssistantCourse:
        """Link the assistant fixture to the course fixture."""
        return AssistantCourseFactory(assistant=assistant, course=course)

    def test_assistant_lists_own_course_questions(self, client, assistant, assistant_course, course, auth_headers):
        q = MCQuestionFactory(course=course)
        resp = client.get(f"/api/v1/admin/multichoice/questions?course_id={course.id}", **auth_headers(assistant))
        assert resp.status_code == 200
        assert any(item["id"] == q.id for item in resp.json())

    def test_assistant_unfiltered_list_scoped_to_own_courses(
        self, client, assistant, assistant_course, course, auth_headers
    ):
        own = MCQuestionFactory(course=course)
        foreign = MCQuestionFactory()  # a different course
        resp = client.get("/api/v1/admin/multichoice/questions", **auth_headers(assistant))
        assert resp.status_code == 200
        ids = {item["id"] for item in resp.json()}
        assert own.id in ids
        assert foreign.id not in ids

    def test_assistant_cannot_touch_foreign_course(self, client, assistant, assistant_course, course, auth_headers):
        foreign = MCQuestionFactory()  # a different course
        other_course_id = foreign.course_id
        # A filtered list for a course the assistant does not support is a 404.
        assert (
            client.get(
                f"/api/v1/admin/multichoice/questions?course_id={other_course_id}", **auth_headers(assistant)
            ).status_code
            == 404
        )
        # And the foreign question itself is invisible for update/delete.
        assert (
            client.put(
                f"/api/v1/admin/multichoice/questions/{foreign.id}",
                {"text": "hacked"},
                content_type="application/json",
                **auth_headers(assistant),
            ).status_code
            == 404
        )
        assert (
            client.delete(f"/api/v1/admin/multichoice/questions/{foreign.id}", **auth_headers(assistant)).status_code
            == 404
        )

    def test_assistant_creates_card_and_sheet(self, client, assistant, assistant_course, course, auth_headers):
        qs = [MCQuestionFactory(course=course) for _ in range(2)]
        resp = client.post(
            f"/api/v1/admin/multichoice/cards?course_id={course.id}",
            {"title": "Assistant card", "question_ids": [q.id for q in qs]},
            content_type="application/json",
            **auth_headers(assistant),
        )
        assert resp.status_code == 200, resp.content
        card_id = resp.json()["id"]

        student = UserFactory(course=course)
        start, end = _open_window()
        resp = client.post(
            "/api/v1/admin/multichoice/sheets",
            {
                "card_id": card_id,
                "course_id": course.id,
                "window_start": start,
                "window_end": end,
                "number": 1,
                "student_ids": [student.id],
            },
            content_type="application/json",
            **auth_headers(assistant),
        )
        assert resp.status_code == 200, resp.content
        assert resp.json()["student_ids"] == [student.id]

    def test_assistant_cannot_create_in_foreign_course(self, client, assistant, assistant_course, course, auth_headers):
        other = MCQuestionFactory()
        resp = client.post(
            f"/api/v1/admin/multichoice/cards?course_id={other.course_id}",
            {"title": "Nope", "question_ids": [other.id]},
            content_type="application/json",
            **auth_headers(assistant),
        )
        assert resp.status_code == 404

    def test_student_cannot_use_mc_admin(self, client, student, assistant_course, course, auth_headers):
        resp = client.get(f"/api/v1/admin/multichoice/questions?course_id={course.id}", **auth_headers(student))
        assert resp.status_code == 403
