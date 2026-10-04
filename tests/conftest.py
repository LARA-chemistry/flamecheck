"""
Pytest fixtures for the FlameCheck test suite.

All fixtures are built with the factory-boy factories that live in each app
(``users.factory``, ``substances.factory``, ``config.factory``,
``analyses.factory``). The fixture *names* are kept stable so the individual
test modules do not need to change; only the construction mechanism has moved
from hand-written ``objects.create(...)`` calls to factories.
"""

from __future__ import annotations

import uuid

import pytest
from analyses.factory import AnalysisInstanceFactory, AnalysisTypeFactory
from analyses.models import AnalysisInstance, AnalysisType
from config.factory import CourseFactory, GradingConfigFactory
from config.models import Course, GradingConfig
from substances.factory import IonFactory, create_ion_catalog
from substances.models import Ion
from users.factory import (
    AdminUserFactory,
    AssistantUserFactory,
    StudentBarcodeFactory,
    UserFactory,
)
from users.models import StudentBarcode, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(db) -> User:
    """A student user (the default factory role)."""
    return UserFactory(username="student1", first_name="Test", last_name="Student", matriculation_no="12345")


@pytest.fixture
def student2(db) -> User:
    """A second student user."""
    return UserFactory(username="student2", first_name="Second", last_name="Student")


@pytest.fixture
def assistant(db) -> User:
    """An assistant user."""
    return AssistantUserFactory(username="assistant1", first_name="Test", last_name="Assistant")


@pytest.fixture
def admin_user(db) -> User:
    """An admin user (staff + superuser + admin role)."""
    return AdminUserFactory(username="admin1", email="admin@example.com", first_name="Admin")


@pytest.fixture
def student_barcode(student) -> StudentBarcode:
    """A personal barcode for the student fixture."""
    return StudentBarcodeFactory(student=student, value="FC-1-abc12345")


@pytest.fixture
def course(db) -> Course:
    """An active course."""
    return CourseFactory(name="Inorganic Chemistry WS 2026", semester="WS 2026", is_active=True)


@pytest.fixture
def ions(db) -> list[Ion]:
    """A small ion catalog (6 cations, 4 anions) built from the factory catalog."""
    return create_ion_catalog(
        [
            "sodium",
            "potassium",
            "ammonium",
            "magnesium",
            "calcium",
            "copper",
            "chloride",
            "bromide",
            "sulfate",
            "carbonate",
        ]
    )


@pytest.fixture
def analysis_type(ions) -> AnalysisType:
    """An analysis type whose possible set covers the whole ion fixture."""
    return AnalysisTypeFactory(name="Analysis 3", description="Cations I-II & anions", possible_ions=ions)


@pytest.fixture
def analysis_instance(analysis_type, course, ions) -> AnalysisInstance:
    """An analysis instance with an open window and a 3-ion correct set."""
    correct = [IonFactory.make(name) for name in ("ammonium", "sulfate", "copper")]
    return AnalysisInstanceFactory(
        type=analysis_type,
        course=course,
        number=3,
        correct_ions=correct,  # default window is open
    )


@pytest.fixture
def assigned_instance(analysis_instance, student, course) -> AnalysisInstance:
    """An analysis instance assigned to the student fixture."""
    from users.factory import StudentAssignmentFactory

    StudentAssignmentFactory(course=course, student=student, instance=analysis_instance, number=3)
    return analysis_instance


@pytest.fixture
def grading_config(db) -> GradingConfig:
    """The singleton grading configuration (defaults)."""
    return GradingConfigFactory()


@pytest.fixture
def auth_headers():
    """Build an ``HTTP_AUTHORIZATION`` header dict for a user (fresh token each call)."""
    from users import jwt

    def _make(user) -> dict:
        token = jwt.issue_token(user, jwt.ACCESS_TOKEN)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    return _make


@pytest.fixture
def idempotency_key() -> str:
    """A fresh, client-style idempotency key (UUID hex)."""
    return uuid.uuid4().hex
