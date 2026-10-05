"""
Factory-boy definitions for the ``users`` app models.

Factories live inside each Django app so they can be imported wherever the
domain logic is tested. They are only used by the test-suite (``tests/``); they
are safe to import in production because importing them has no side-effects.

The module exercises the full factory-boy / Faker toolbox:

- ``Faker``          - realistic random values (names, emails, matriculation numbers).
- ``Sequence``       - guaranteed-unique values per factory invocation.
- ``SubFactory``     - build related objects inline (barcodes, assignments).
- ``django_get_or_create`` - idempotent creation keyed on ``username``.
- ``post_generation`` - optional FK (``course``) handled cleanly.
- Custom ``_create`` - routes through ``create_user``/``create_superuser`` so
  passwords are hashed, plus ``AdminUserFactory`` / ``AssistantUserFactory``
  sub-factories for the common role cases.

``User`` is a custom :class:`~django.contrib.auth.models.AbstractUser` with the
abstract ``first_name``/``last_name`` fields redefined as plain ``CharField``s,
so the factory populates them directly with Faker values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from factory import Faker, Sequence, SubFactory, post_generation
from factory.django import DjangoModelFactory

from .models import LoginAttempt, StudentAssignment, StudentBarcode, User

if TYPE_CHECKING:
    pass


class UserFactory(DjangoModelFactory):
    """Factory for :class:`users.models.User`."""

    class Meta:
        """Meta options for :class:`UserFactory`."""

        model = User
        django_get_or_create = ("username",)

    # -- identity ----------------------------------------------------------
    username = Sequence(lambda n: f"user{n}")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    email = Faker("email")
    # A 5-digit matriculation number as a string (the model field is a CharField).
    # ``bothify`` with ``#`` placeholders yields a digit string, e.g. "48291".
    matriculation_no = Faker("bothify", text="#####")
    lab = Faker("company")
    labspace_id = Sequence(lambda n: f"LS-{n:06d}")
    telephone = Faker("phone_number")

    # -- password / auth ---------------------------------------------------
    # Use Django's create_user()/create_superuser() so the password is hashed
    # properly (the plain model() path would store it in cleartext).
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123")
        manager = model_class._default_manager
        if kwargs.pop("is_superuser", False):
            user = manager.create_superuser(
                username=kwargs.pop("username"), email=kwargs.pop("email"), password=password, **kwargs
            )
        else:
            user = manager.create_user(
                username=kwargs.pop("username"), email=kwargs.pop("email"), password=password, **kwargs
            )
        return user

    # -- role --------------------------------------------------------------
    # `role` is a plain, overridable field (default: student). For the common
    # "make me an admin / assistant" case, use the SubFactory helpers below or
    # pass ``role=`` explicitly:
    #     UserFactory(role=User.Role.ASSISTANT)
    #     AdminUserFactory()
    role = User.Role.STUDENT

    # -- optional course enrollment ---------------------------------------
    @post_generation
    def course(obj, create, extracted, **kwargs):
        """Optionally enroll the user in a course."""
        if not create:
            return
        if extracted is None:
            return
        if isinstance(extracted, list):
            extracted = extracted[0]
        obj.course = extracted
        obj.save()


class StudentBarcodeFactory(DjangoModelFactory):
    """Factory for :class:`users.models.StudentBarcode`."""

    class Meta:
        """Meta options for :class:`StudentBarcodeFactory`."""

        model = StudentBarcode
        django_get_or_create = ("value",)

    student = SubFactory(UserFactory)
    # Value must be unique and follow the 'FC-<id>-<uuid8>' convention.
    value = Sequence(lambda n: f"FC-{n}-{Faker('hex_digit', times=8)}")
    active = True
    created_at = Faker("date_time_this_year", before_now=True)


class LoginAttemptFactory(DjangoModelFactory):
    """Factory for :class:`users.models.LoginAttempt`."""

    class Meta:
        """Meta options for :class:`LoginAttemptFactory`."""

        model = LoginAttempt

    username = Faker("user_name")
    ip_address = Faker("ipv4")
    success = Faker("boolean", chance_of_getting_true=30)
    attempted_at = Faker("date_time_this_year", before_now=True)


class StudentAssignmentFactory(DjangoModelFactory):
    """Factory for :class:`users.models.StudentAssignment`."""

    class Meta:
        """Meta options for :class:`StudentAssignmentFactory`."""

        model = StudentAssignment
        django_get_or_create = ("student", "instance")

    course = SubFactory("config.factory.CourseFactory")
    student = SubFactory(UserFactory)
    instance = SubFactory("analyses.factory.AnalysisInstanceFactory")
    number = Faker("pyint", min_value=1, max_value=4)


class AdminUserFactory(UserFactory):
    """A ready-made admin (staff + superuser + ``role='admin'``)."""

    role = User.Role.ADMIN
    is_staff = True
    is_superuser = True


class AssistantUserFactory(UserFactory):
    """A ready-made assistant."""

    role = User.Role.ASSISTANT
