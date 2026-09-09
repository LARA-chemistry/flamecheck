"""Pytest fixtures for the FlameCheck test suite."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from users.models import StudentAssignment, StudentBarcode, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(db) -> User:
    """A student user."""
    return User.objects.create_user(
        username="student1",
        password="testpass123",
        name="Test Student",
        role=User.Role.STUDENT,
        matriculation_no="12345",
    )


@pytest.fixture
def student2(db) -> User:
    """A second student user."""
    return User.objects.create_user(
        username="student2",
        password="testpass123",
        name="Second Student",
        role=User.Role.STUDENT,
    )


@pytest.fixture
def assistant(db) -> User:
    """An assistant user."""
    return User.objects.create_user(
        username="assistant1",
        password="testpass123",
        name="Test Assistant",
        role=User.Role.ASSISTANT,
    )


@pytest.fixture
def admin_user(db) -> User:
    """An admin user."""
    return User.objects.create_superuser(
        username="admin1",
        email="admin@example.com",
        password="testpass123",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def student_barcode(student: User) -> StudentBarcode:
    """A personal barcode for the student fixture."""
    return StudentBarcode.objects.create(student=student, value="FC-1-abc12345")


@pytest.fixture
def course(db):
    """An active course."""
    from config.models import Course

    return Course.objects.create(name="Inorganic Chemistry WS 2026", semester="WS 2026", is_active=True)


@pytest.fixture
def ions(db):
    """A small ion catalog (6 cations, 4 anions)."""
    from substances.models import Ion

    cations = [
        Ion.objects.create(symbol=s, name=n, charge=c, kind="cation", group=g)
        for s, n, c, g in [
            ("Na+", "Sodium", 1, "Group V"),
            ("K+", "Potassium", 1, "Group V"),
            ("NH4+", "Ammonium", 1, "Group I"),
            ("Mg2+", "Magnesium", 2, "Group IV"),
            ("Ca2+", "Calcium", 2, "Group IV"),
            ("Cu2+", "Copper(II)", 2, "Group II"),
        ]
    ]
    anions = [
        Ion.objects.create(symbol=s, name=n, charge=c, kind="anion", group=g)
        for s, n, c, g in [
            ("Cl-", "Chloride", -1, "Halides"),
            ("Br-", "Bromide", -1, "Halides"),
            ("SO4-2", "Sulfate", -2, "Oxyanions"),
            ("CO3-2", "Carbonate", -2, "Oxyanions"),
        ]
    ]
    return cations + anions


@pytest.fixture
def analysis_type(ions) -> "object":
    """An analysis type whose possible set covers the whole ion fixture."""
    from analyses.models import AnalysisType

    t = AnalysisType.objects.create(name="Analysis 3", description="Cations I–II & anions")
    t.possible_ions.set(ions)
    return t


def _open_window() -> tuple:
    now = timezone.now()
    return (now - timedelta(hours=1), now + timedelta(hours=1))


@pytest.fixture
def analysis_instance(analysis_type, course, ions):
    """An analysis instance with an open window and a 3-ion correct set."""
    from analyses.models import AnalysisInstance
    from substances.models import Ion

    start, end = _open_window()
    inst = AnalysisInstance.objects.create(
        type=analysis_type,
        course=course,
        number=3,
        window_start=start,
        window_end=end,
    )
    inst.correct_ions.set(Ion.objects.filter(symbol__in=["NH4+", "SO4-2", "Cu2+"]))
    return inst


@pytest.fixture
def assigned_instance(analysis_instance, student, course):
    """An analysis instance assigned to the student fixture."""
    StudentAssignment.objects.create(
        course=course,
        student=student,
        instance=analysis_instance,
        number=3,
    )
    return analysis_instance


@pytest.fixture
def grading_config(db) -> "object":
    """The singleton grading configuration (defaults)."""
    from config.models import GradingConfig

    return GradingConfig.get_instance()


@pytest.fixture
def auth_headers():
    """Build an ``HTTP_AUTHORIZATION`` header dict for a user."""
    from users import jwt

    def _make(user: User) -> dict:
        token = jwt.issue_token(user, jwt.ACCESS_TOKEN)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    return _make


@pytest.fixture
def idempotency_key() -> str:
    return uuid.uuid4().hex
