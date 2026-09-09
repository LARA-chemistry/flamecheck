"""
Ninja API views for the substances app.

Read access to ions/substances is open to any authenticated user (students
need them to render their analysis). Mutating endpoints are admin-only.
"""

from __future__ import annotations

from ninja import Router
from ninja.errors import AuthenticationError, HttpError, ValidationError
from substances.api.schemas import IonIn, IonOut, SubstanceIn, SubstanceOut, ion_to_schema, substance_to_schema
from substances.models import Ion, Substance

router = Router(tags=["substances"])


def _require_admin(request) -> None:
    """Raise unless the request user is an admin."""
    if not (getattr(request.user, "is_admin", False)):
        raise AuthenticationError(403, "Admin role required.")


@router.get("/ions", response=list[IonOut])
def list_ions(request, kind: str | None = None, group: str | None = None):
    """List all ions, optionally filtered by kind (cation/anion) and group."""
    qs = Ion.objects.all()
    if kind:
        qs = qs.filter(kind=kind)
    if group:
        qs = qs.filter(group=group)
    return [ion_to_schema(i) for i in qs]


@router.get("/ions/{ion_id}", response=IonOut)
def get_ion(request, ion_id: int):
    """Return a single ion."""
    return ion_to_schema(Ion.objects.get(pk=ion_id))


@router.get("/substances", response=list[SubstanceOut])
def list_substances(request, ion_id: int | None = None):
    """List all substances, optionally restricted to those containing ``ion_id``."""
    qs = Substance.objects.all().prefetch_related("ions")
    if ion_id is not None:
        qs = Substance.objects.with_ion(ion_id).prefetch_related("ions")
    return [substance_to_schema(s) for s in qs]


@router.get("/substances/{substance_id}", response=SubstanceOut)
def get_substance(request, substance_id: int):
    """Return a single substance with its ion breakdown."""
    substance = Substance.objects.filter(pk=substance_id).prefetch_related("ions").first()
    if substance is None:
        raise HttpError(404, "Substance not found.")
    return substance_to_schema(substance)


@router.post("/ions", response=IonOut)
def create_ion(request, payload: IonIn):
    """Create a new ion (admin only)."""
    _require_admin(request)
    ion = Ion.objects.create(
        symbol=payload.symbol,
        name=payload.name,
        charge=payload.charge,
        kind=payload.kind,
        group=payload.group,
    )
    return ion_to_schema(ion)


@router.put("/ions/{ion_id}", response=IonOut)
def update_ion(request, ion_id: int, payload: IonIn):
    """Update an ion (admin only)."""
    _require_admin(request)
    ion = Ion.objects.get(pk=ion_id)
    ion.symbol = payload.symbol
    ion.name = payload.name
    ion.charge = payload.charge
    ion.kind = payload.kind
    ion.group = payload.group
    ion.save()
    return ion_to_schema(ion)


@router.delete("/ions/{ion_id}", response=None)
def delete_ion(request, ion_id: int):
    """Delete an ion that is not referenced by any analysis (admin only)."""
    _require_admin(request)
    ion = Ion.objects.get(pk=ion_id)
    if ion.analysis_types.exists() or ion.instances.exists():
        raise ValidationError({"id": ["Ion is referenced by an analysis and cannot be deleted."]})
    ion.delete()


@router.post("/substances", response=SubstanceOut)
def create_substance(request, payload: SubstanceIn):
    """Create a new substance (admin only)."""
    _require_admin(request)
    substance = Substance.objects.create(
        name=payload.name,
        synonyms=payload.synonyms or [],
        formula=payload.formula or "",
        pubchem_id=payload.pubchem_id or "",
        wikipedia_link=payload.wikipedia_link or "",
    )
    if payload.ion_ids:
        substance.ions.set(payload.ion_ids)
    return substance_to_schema(substance)


@router.put("/substances/{substance_id}", response=SubstanceOut)
def update_substance(request, substance_id: int, payload: SubstanceIn):
    """Update a substance (admin only)."""
    _require_admin(request)
    substance = Substance.objects.get(pk=substance_id)
    substance.name = payload.name
    substance.synonyms = payload.synonyms if payload.synonyms is not None else substance.synonyms
    substance.formula = payload.formula if payload.formula is not None else substance.formula
    substance.pubchem_id = payload.pubchem_id if payload.pubchem_id is not None else substance.pubchem_id
    substance.wikipedia_link = (
        payload.wikipedia_link if payload.wikipedia_link is not None else substance.wikipedia_link
    )
    substance.save()
    if payload.ion_ids is not None:
        substance.ions.set(payload.ion_ids)
    return substance_to_schema(substance)


@router.delete("/substances/{substance_id}", response=None)
def delete_substance(request, substance_id: int):
    """Delete a substance (admin only)."""
    _require_admin(request)
    Substance.objects.get(pk=substance_id).delete()
