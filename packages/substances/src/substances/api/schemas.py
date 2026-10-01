"""Ninja schemas for the substances API."""

from __future__ import annotations

from typing import Any

from ninja import Schema


class IonOut(Schema):
    """Public representation of an ion."""

    id: int
    symbol: str
    name: str
    charge: int
    kind: str
    group: str


class IonIn(Schema):
    """Payload for creating/updating an ion (admin)."""

    symbol: str
    name: str
    charge: int = 0
    kind: str
    group: str = ""


class SubstanceOut(Schema):
    """Public representation of a substance."""

    id: int
    name: str
    synonyms: list[str]
    formula: str
    ions: list[IonOut]
    pubchem_id: str
    wikipedia_link: str


class SubstanceIn(Schema):
    """Payload for creating/updating a substance (admin)."""

    name: str
    synonyms: list[str] | None = None
    formula: str | None = None
    ion_ids: list[int] | None = None
    pubchem_id: str | None = None
    wikipedia_link: str | None = None


class ImportCsvOut(Schema):
    """Summary of a CSV import run (admin)."""

    created: int
    updated: int
    skipped: int
    total_rows: int
    missing_ions: list[str]
    errors: list[str]


def ion_to_schema(ion: Any) -> dict:
    """Convert an :class:`~substances.models.Ion` to its schema dict."""
    return {
        "id": ion.id,
        "symbol": ion.symbol,
        "name": ion.name,
        "charge": ion.charge,
        "kind": ion.kind,
        "group": ion.group or "",
    }


def substance_to_schema(substance: Any) -> dict:
    """Convert a :class:`~substances.models.Substance` to its schema dict."""
    return {
        "id": substance.id,
        "name": substance.name,
        "synonyms": substance.synonyms or [],
        "formula": substance.formula or "",
        "ions": [ion_to_schema(i) for i in substance.ions.all()],
        "pubchem_id": substance.pubchem_id or "",
        "wikipedia_link": substance.wikipedia_link or "",
    }
