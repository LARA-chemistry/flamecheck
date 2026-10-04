"""
Factory-boy definitions for the ``substances`` app models (``Ion`` / ``Substance``).

``Ion`` has a unique constraint on ``(symbol, kind)``, so the default ``symbol`` is a
:class:`~factory.Sequence` that guarantees uniqueness across a test run. The
standard first-semester catalog is available through the :data:`ION_CATALOG`
lookup and the :meth:`IonFactory.make` helper / :func:`create_ion_catalog` batch
helper, which build named ions (``sodium``, ``chloride``, ...) with their real
symbol/charge/kind/name/group.

``Substance`` references ions via M2M, handled with :func:`~factory.post_generation`
so the relation is optional and easy to override.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from factory import Faker, LazyAttribute, Sequence, post_generation
from factory.django import DjangoModelFactory

from .models import Ion, Substance

if TYPE_CHECKING:
    pass

# (symbol, name, charge, kind, group) for the standard first-semester catalog.
# Kept as plain data so factories build only real model fields (this keeps
# ``django_get_or_create`` happy and avoids factory-boy trait-expansion quirks).
ION_CATALOG: dict[str, tuple[str, str, int, str, str]] = {
    "sodium": ("Na+1", "Sodium", 1, Ion.Kind.CATION, "Group V"),
    "potassium": ("K+1", "Potassium", 1, Ion.Kind.CATION, "Group V"),
    "ammonium": ("NH4+1", "Ammonium", 1, Ion.Kind.CATION, "Group I"),
    "magnesium": ("Mg+2", "Magnesium", 2, Ion.Kind.CATION, "Group IV"),
    "calcium": ("Ca+2", "Calcium", 2, Ion.Kind.CATION, "Group IV"),
    "copper": ("Cu+2", "Copper(II)", 2, Ion.Kind.CATION, "Group II"),
    "iron2": ("Fe+2", "Iron(II)", 2, Ion.Kind.CATION, "Group II"),
    "iron3": ("Fe+3", "Iron(III)", 3, Ion.Kind.CATION, "Group III"),
    "aluminium": ("Al+3", "Aluminium", 3, Ion.Kind.CATION, "Group III"),
    "zinc": ("Zn+2", "Zinc", 2, Ion.Kind.CATION, "Group II"),
    "manganese": ("Mn+2", "Manganese", 2, Ion.Kind.CATION, "Group II"),
    "barium": ("Ba+2", "Barium", 2, Ion.Kind.CATION, "Group II"),
    "chloride": ("Cl-1", "Chloride", -1, Ion.Kind.ANION, "Halides"),
    "bromide": ("Br-1", "Bromide", -1, Ion.Kind.ANION, "Halides"),
    "iodide": ("I-1", "Iodide", -1, Ion.Kind.ANION, "Halides"),
    "sulfate": ("SO4-2", "Sulfate", -2, Ion.Kind.ANION, "Oxyanions"),
    "sulfite": ("SO3-2", "Sulfite", -2, Ion.Kind.ANION, "Oxyanions"),
    "carbonate": ("CO3-2", "Carbonate", -2, Ion.Kind.ANION, "Oxyanions"),
    "phosphate": ("PO4-3", "Phosphate", -3, Ion.Kind.ANION, "Oxyanions"),
    "nitrate": ("NO3-1", "Nitrate", -1, Ion.Kind.ANION, "Oxyanions"),
    "nitrite": ("NO2-1", "Nitrite", -1, Ion.Kind.ANION, "Oxyanions"),
    "sulfide": ("S-2", "Sulfide", -2, Ion.Kind.ANION, "Chalcogens"),
}


class IonFactory(DjangoModelFactory):
    """Factory for :class:`substances.models.Ion`."""

    class Meta:
        """Meta options for :class:`IonFactory`."""

        model = Ion
        django_get_or_create = ("symbol", "kind")

    # Default: a guaranteed-unique, plausible symbol (override with real values
    # via :meth:`make` or by passing ``symbol=`` / ``kind=`` directly).
    symbol = Sequence(lambda n: f"Ion{n}")
    name = Faker("word")
    charge = 0
    kind = Ion.Kind.CATION
    group = Faker("word")

    @classmethod
    def make(cls, name: str = "sodium", **overrides) -> Ion:
        """
        Build a named ion from :data:`ION_CATALOG` (e.g. ``IonFactory.make('copper')``).

        Extra keyword arguments override any catalog value.

        Args:
            name: A key from :data:`ION_CATALOG` (e.g. ``'sodium'``, ``'chloride'``).
            **overrides: Field overrides applied on top of the catalog values.

        Returns:
            Ion: The created (or existing) ion.

        Raises:
            KeyError: If ``name`` is not in the catalog.

        """
        symbol, ion_name, charge, kind, group = ION_CATALOG[name]
        return cls.create(
            symbol=symbol,
            name=ion_name,
            charge=charge,
            kind=kind,
            group=group,
            **overrides,
        )


def create_ion_catalog(names: list[str] | None = None) -> list[Ion]:
    """
    Create (idempotently) a set of catalog ions.

    Args:
        names: Catalog keys to create. Defaults to the entire :data:`ION_CATALOG`.

    Returns:
        list[Ion]: The created/updated ions, in the requested order.

    """
    if names is None:
        names = list(ION_CATALOG)
    return [IonFactory.make(name) for name in names]


class SubstanceFactory(DjangoModelFactory):
    """Factory for :class:`substances.models.Substance`."""

    class Meta:
        """Meta options for :class:`SubstanceFactory`."""

        model = Substance
        django_get_or_create = ("name",)
        skip_postgeneration_save = True

    name = Faker("company")
    formula = Faker("bothify", text="H?O?")
    # Fresh list per instance (mutable defaults are not shared).
    synonyms = LazyAttribute(lambda obj: [])
    pubchem_id = Sequence(lambda n: str(n + 1000))
    wikipedia_link = Faker("url")

    @post_generation
    def ions(obj, create, extracted, **kwargs):
        """Optionally attach a set of ions to this substance."""
        if not create:
            return
        if extracted is None:
            return
        if isinstance(extracted, list):
            obj.ions.set(extracted)
        else:
            obj.ions.add(extracted)
