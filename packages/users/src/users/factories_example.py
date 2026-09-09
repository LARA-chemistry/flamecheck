"""
Factory definitions for lara_django_base models.

Factories are only available when factory_boy is installed (dev/test environments).
This module can be safely imported in production - factories will simply be None.
"""



from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from factory.django import DjangoModelFactory

try:
    from factory import Faker, Sequence, SubFactory
    from factory.django import DjangoModelFactory

    from .models.base import ExtraData
    from .models.entity import Entity
    from .models.group import Group
    from .models.user import LaraUser

    class EntityFactory(DjangoModelFactory):
        """Factory for creating Entity test instances."""

        class Meta:
            """Meta options for EntityFactory."""

            model = Entity
            django_get_or_create = ("entity_id",)

        entity_id = Sequence(lambda n: f"00000000-0000-0000-0000-{n:012d}")
        name_first = Faker("first_name")
        name_last = Faker("last_name")
        name_full = Sequence(lambda n: f"EntityFullName{n}")
        email = Faker("email")
        orcid = Sequence(lambda n: f"0000-0002-1825-{n:04d}")

    class GroupFactory(DjangoModelFactory):
        """Factory for creating Group test instances."""

        class Meta:
            """Meta options for GroupFactory."""

            model = Group
            django_get_or_create = ("group_id",)

        group_id = Sequence(lambda n: f"00000000-0000-0000-0000-{n:012d}")
        name = Sequence(lambda n: f"GroupName{n}")
        name_full = Sequence(lambda n: f"GroupFullName{n}")
        description = Faker("sentence")

    class LaraUserFactory(DjangoModelFactory):
        """Factory for creating LaraUser test instances."""

        class Meta:
            """Meta options for LaraUserFactory."""

            model = LaraUser
            django_get_or_create = ("larauser_id",)

        larauser_id = Sequence(lambda n: f"00000000-0000-0000-0000-{n:012d}")
        username = Sequence(lambda n: f"user{n}")
        email = Faker("email")
        first_name = Faker("first_name")
        last_name = Faker("last_name")
        entity = SubFactory(EntityFactory)

    class ExtraDataFactory(DjangoModelFactory):
        """Factory for creating ExtraData test instances."""

        class Meta:
            """Meta options for ExtraDataFactory."""

            model = ExtraData
            django_get_or_create = ("extradata_id",)

        extradata_id = Sequence(lambda n: f"00000000-0000-0000-0000-{n:012d}")
        email = Faker("email")
        name = Sequence(lambda n: f"ExtraDataName{n}")


    def create_demo_data(n: int = 1):
        """Create demo data for testing purposes."""
        EntityFactory.create_batch(n)
        GroupFactory.create_batch(n)
        LaraUserFactory.create_batch(n)
        # ExtraDataFactory.create_batch(n)

except ImportError:
    EntityFactory = None
    GroupFactory = None
    LaraUserFactory = None
    ExtraDataFactory = None

    def create_demo_data(n: int = 1):
        """Stub function when factory_boy is not available."""
        raise RuntimeError("factory_boy is not installed - cannot create demo data")

