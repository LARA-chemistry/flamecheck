"""Tests for the multiple-choice domain models and grading."""

from __future__ import annotations

from datetime import timedelta

import pytest
from config.factory import CourseFactory
from config.models import GradingConfig
from django.core.exceptions import ValidationError
from django.utils import timezone
from multichoice.factory import (
    MCCardFactory,
    MCQuestionFactory,
    MCSheetFactory,
    MCStudentAssignmentFactory,
)
from multichoice.models import MAX_QUESTIONS_PER_CARD, MCSheet

pytestmark = pytest.mark.django_db


class TestCardConstraints:
    def test_card_allows_up_to_three_questions(self) -> None:
        course = CourseFactory()
        questions = [MCQuestionFactory(course=course) for _ in range(MAX_QUESTIONS_PER_CARD)]
        card = MCCardFactory(course=course, questions=questions)
        card.full_clean()  # exactly 3 questions is allowed

    def test_card_rejects_four_questions(self) -> None:
        course = CourseFactory()
        questions = [MCQuestionFactory(course=course) for _ in range(MAX_QUESTIONS_PER_CARD + 1)]
        card = MCCardFactory(course=course, questions=questions)
        with pytest.raises(ValidationError):
            card.clean()

    def test_question_count_and_order(self) -> None:
        course = CourseFactory()
        q0 = MCQuestionFactory(course=course, text="Q0")
        q1 = MCQuestionFactory(course=course, text="Q1")
        card = MCCardFactory(course=course, questions=[q0, q1])
        assert card.question_count() == 2
        assert [q.text for q in card.questions()] == ["Q0", "Q1"]


class TestWindowStatus:
    def test_too_early(self) -> None:
        now = timezone.now()
        sheet = MCSheetFactory(window_start=now + timedelta(hours=1), window_end=now + timedelta(hours=2))
        assert sheet.window_status() == "too_early"

    def test_too_late(self) -> None:
        now = timezone.now()
        sheet = MCSheetFactory(window_start=now - timedelta(hours=2), window_end=now - timedelta(hours=1))
        assert sheet.window_status() == "too_late"

    def test_open(self) -> None:
        now = timezone.now()
        sheet = MCSheetFactory(window_start=now - timedelta(hours=1), window_end=now + timedelta(hours=1))
        assert sheet.window_status() == "open"

    def test_submitted(self) -> None:
        from users.factory import UserFactory

        sheet = MCSheetFactory()
        student = UserFactory()
        MCStudentAssignmentFactory(sheet=sheet, student=student, course=sheet.course)
        sheet.submit(student, {q.id: q.correct_option().id for q in sheet.questions()}, idempotency_key="k1")
        assert sheet.window_status() == "submitted"


class TestGrading:
    def _sheet_with_grading(self, points: int, penalty: int) -> MCSheet:
        course = CourseFactory()
        sheet = MCSheetFactory(course=course)
        gc = GradingConfig.get_for_course(course)
        gc.mc_points_per_card = points
        gc.mc_penalty_per_wrong = penalty
        gc.save()
        return sheet

    def test_all_correct_awards_full_points(self) -> None:
        sheet = self._sheet_with_grading(10, 2)
        answers = {q.id: q.correct_option().id for q in sheet.questions()}
        sub = sheet.submit(self._student(sheet), answers, idempotency_key="a")
        assert sub.score == 10
        assert sub.wrong_count == 0

    def test_penalty_per_wrong_answer(self) -> None:
        # Build a card with three questions so a single wrong answer is unambiguous.
        course = CourseFactory()
        from multichoice.factory import MCCardFactory

        questions = [MCQuestionFactory(course=course) for _ in range(3)]
        card = MCCardFactory(course=course, questions=questions)
        sheet = MCSheetFactory(card=card, course=course)
        gc = GradingConfig.get_for_course(course)
        gc.mc_points_per_card = 10
        gc.mc_penalty_per_wrong = 2
        gc.save()
        student = self._student(sheet)
        answers = {q.id: q.correct_option().id for q in questions}
        # Wrongly answer the first question (pick a non-correct option).
        first = questions[0]
        wrong_opt = first.options_set.filter(is_correct=False).first()
        answers[first.id] = wrong_opt.id
        sub = sheet.submit(student, answers, idempotency_key="a")
        assert sub.wrong_count == 1
        assert sub.correct_count == 2
        assert sub.score == 8  # 10 - 2*1

    def test_score_floors_at_zero(self) -> None:
        course = CourseFactory()
        from multichoice.factory import MCCardFactory

        questions = [MCQuestionFactory(course=course) for _ in range(3)]
        card = MCCardFactory(course=course, questions=questions)
        sheet = MCSheetFactory(card=card, course=course)
        gc = GradingConfig.get_for_course(course)
        gc.mc_points_per_card = 4
        gc.mc_penalty_per_wrong = 2
        gc.save()
        student = self._student(sheet)
        answers = {}
        for q in questions:
            answers[q.id] = q.options_set.filter(is_correct=False).first().id
        sub = sheet.submit(student, answers, idempotency_key="a")
        assert sub.score == 0  # 4 - 2*3 = -2 -> floored to 0

    def _student(self, sheet: MCSheet):
        from users.factory import UserFactory

        student = UserFactory()
        MCStudentAssignmentFactory(sheet=sheet, student=student, course=sheet.course)
        return student


class TestSubmission:
    def test_requires_all_questions_answered(self) -> None:
        sheet = MCSheetFactory()
        student = self._student(sheet)
        questions = sheet.questions()
        if len(questions) == 1:
            # A single question: submitting nothing must fail.
            with pytest.raises(ValidationError):
                sheet.submit(student, {}, idempotency_key="a")
        else:
            answers = {q.id: q.correct_option().id for q in questions}
            del answers[questions[0].id]
            with pytest.raises(ValidationError):
                sheet.submit(student, answers, idempotency_key="a")

    def test_rejects_option_not_belonging_to_question(self) -> None:
        sheet = MCSheetFactory()
        student = self._student(sheet)
        q = sheet.questions()[0]
        other = MCQuestionFactory(course=sheet.course)
        answers = {q.id: other.correct_option().id}
        with pytest.raises(ValidationError):
            sheet.submit(student, answers, idempotency_key="a")

    def test_idempotency_returns_original(self) -> None:
        sheet = MCSheetFactory()
        student = self._student(sheet)
        answers = {q.id: q.correct_option().id for q in sheet.questions()}
        first = sheet.submit(student, answers, idempotency_key="same")
        second = sheet.submit(student, answers, idempotency_key="same")
        assert first.id == second.id
        assert sheet.submissions.count() == 1

    def _student(self, sheet: MCSheet):
        from users.factory import UserFactory

        student = UserFactory()
        MCStudentAssignmentFactory(sheet=sheet, student=student, course=sheet.course)
        return student
