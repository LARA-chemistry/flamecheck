"""
Tests for the factory-boy / Faker fixtures themselves.

These tests exercise the factories (and, through them, factory-boy and Faker)
to their full extent: sequence uniqueness, Faker realism, ``SubFactory`` graph
building, ``post_generation`` M2M handling, ``django_get_or_create`` idempotency,
named catalog helpers, ``create_batch``, and window-state helpers. They double as
living documentation of how the test data is constructed.
"""

import pytest
from analyses.factory import AnalysisInstanceFactory, AnalysisTypeFactory, SubmissionFactory
from config.factory import AssistantCourseFactory, CourseFactory, GradingConfigFactory
from substances.factory import IonFactory, SubstanceFactory, create_ion_catalog
from users.factory import (
    AdminUserFactory,
    AssistantUserFactory,
    LoginAttemptFactory,
    StudentBarcodeFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


class TestUserFactories:
    """User / role / barcode / login-attempt factories."""

    def test_student_is_default_role(self):
        user = UserFactory()
        assert user.is_student
        assert not user.is_staff

    def test_admin_and_assistant_subfactories(self):
        admin = AdminUserFactory()
        assistant = AssistantUserFactory()
        assert admin.is_admin and admin.is_staff and admin.is_superuser
        assert assistant.is_assistant and not assistant.is_admin

    def test_password_is_hashed(self):
        user = UserFactory()
        # A real Django password hash, never the cleartext default.
        assert user.check_password("testpass123")
        assert "testpass123" not in user.password

    def test_username_is_unique_sequence(self):
        users = UserFactory.create_batch(3)
        usernames = {u.username for u in users}
        assert len(usernames) == 3  # Sequence guarantees no collisions

    def test_faker_fields_are_populated(self):
        user = UserFactory()
        assert "@" in user.email
        assert user.first_name
        assert user.last_name
        assert user.full_name
        assert user.labspace_id.startswith("LS-")

    def test_matriculation_no_is_a_numeric_string(self):
        # Regression: matriculation_no must be a real 5-digit number (as a
        # string, the field is a CharField), never a Faker declaration repr.
        user = UserFactory()
        assert user.matriculation_no
        assert user.matriculation_no.isdigit()
        assert len(user.matriculation_no) == 5
        assert "Faker" not in user.matriculation_no

    def test_barcode_belongs_to_student_and_unique(self):
        student = UserFactory()
        code = StudentBarcodeFactory(student=student)
        assert code.student == student
        assert code.value.startswith("FC-")
        # A second barcode for the same student gets a different value.
        other = StudentBarcodeFactory(student=student)
        assert other.value != code.value

    def test_course_post_generation(self, course):
        user = UserFactory(course=course)
        assert user.course == course

    def test_login_attempt_fakers(self):
        attempt = LoginAttemptFactory()
        assert attempt.username
        assert ":" in attempt.ip_address or attempt.ip_address.count(".") == 3
        assert isinstance(attempt.success, bool)


class TestSubstanceFactories:
    """Ion / Substance factories and the named catalog."""

    def test_default_ion_is_unique_cation(self):
        a, b = IonFactory.create_batch(2)
        assert a.kind == "cation" and b.kind == "cation"
        assert a.symbol != b.symbol  # Sequence-driven uniqueness

    def test_named_catalog_ions(self):
        sodium = IonFactory.make("sodium")
        chloride = IonFactory.make("chloride")
        assert (sodium.symbol, sodium.charge, sodium.kind) == ("Na+1", 1, "cation")
        assert (chloride.symbol, chloride.charge, chloride.kind) == ("Cl-1", -1, "anion")

    def test_catalog_idempotent(self):
        # Same (symbol, kind) -> same object (django_get_or_create).
        a = IonFactory.make("copper")
        b = IonFactory.make("copper")
        assert a.id == b.id

    def test_create_ion_catalog_batch(self):
        ions = create_ion_catalog(["sodium", "potassium", "chloride", "sulfate"])
        assert {i.symbol for i in ions} == {"Na+1", "K+1", "Cl-1", "SO4-2"}

    def test_unknown_catalog_name_raises(self):
        with pytest.raises(KeyError):
            IonFactory.make("not-an-ion")

    def test_substance_m2m_ions(self):
        na = IonFactory.make("sodium")
        cl = IonFactory.make("chloride")
        sub = SubstanceFactory(name="Sodium chloride", formula="NaCl", ions=[na, cl])
        assert set(sub.ions.all()) == {na, cl}

    def test_substance_defaults(self):
        sub = SubstanceFactory()
        assert sub.name
        assert sub.formula
        assert sub.pubchem_id


class TestConfigFactories:
    """Course / grading / assistant-course factories."""

    def test_course_fields(self):
        course = CourseFactory()
        assert course.name
        assert course.is_active

    def test_grading_config_is_singleton_pk1(self):
        a = GradingConfigFactory()
        b = GradingConfigFactory()
        assert a.pk == b.pk == 1
        assert a.points_per_correct_ion == 10

    def test_grading_config_overridable_fields(self):
        gc = GradingConfigFactory(grading_mode="per_analysis", max_submissions_per_analysis=1)
        assert gc.grading_mode == "per_analysis"
        assert gc.max_submissions_per_analysis == 1

    def test_assistant_course_links(self):
        ac = AssistantCourseFactory()
        assert ac.assistant.is_assistant
        assert ac.course is not None


class TestAnalysisFactories:
    """Analysis type / instance / submission factories and window states."""

    def test_analysis_type_possible_ions(self):
        ions = [IonFactory.make(n) for n in ("sodium", "copper", "chloride")]
        at = AnalysisTypeFactory(possible_ions=ions)
        assert set(at.possible_ions.all()) == set(ions)

    def test_instance_default_window_is_open(self):
        inst = AnalysisInstanceFactory()
        assert inst.window_status() == "open"

    def test_window_state_helper(self):
        assert AnalysisInstanceFactory.make("open").window_status() == "open"
        assert AnalysisInstanceFactory.make("too_early").window_status() == "too_early"
        assert AnalysisInstanceFactory.make("too_late").window_status() == "too_late"

    def test_correct_ions_post_generation(self):
        correct = [IonFactory.make(n) for n in ("ammonium", "sulfate", "copper")]
        inst = AnalysisInstanceFactory(correct_ions=correct)
        assert set(inst.correct_ions.all()) == set(correct)

    def test_submission_graph_and_idempotency(self):
        student = UserFactory()
        inst = AnalysisInstanceFactory()
        sub = SubmissionFactory(analysis_instance=inst, student=student, selected_ions=[IonFactory.make("sodium")])
        assert sub.analysis_instance == inst
        assert sub.student == student
        assert sub.submission_number == 1
        # idempotency_key is auto-generated (UUID hex).
        assert len(sub.idempotency_key) == 32

    def test_full_graph_single_call(self):
        # A single factory call builds the whole object graph via SubFactory.
        sub = SubmissionFactory()
        assert sub.analysis_instance.type is not None
        assert sub.analysis_instance.course is not None
        assert sub.student.is_student
