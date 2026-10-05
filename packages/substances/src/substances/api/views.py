"""
Ninja API views for the substances app.

Read access to ions/substances is open to any authenticated user (students
need them to render their analysis). Mutating endpoints are admin-only.
"""

from __future__ import annotations

import csv
import io
import logging

from django.http import HttpResponse
from ninja import Router, UploadedFile
from ninja.errors import AuthenticationError, HttpError, ValidationError
from substances.api.schemas import (
    ImportCsvOut,
    IonIn,
    IonOut,
    SubstanceIn,
    SubstanceOut,
    ion_to_schema,
    substance_to_schema,
)
from substances.ions import IonSymbolError, canonical_symbol, parse_ion
from substances.models import Ion, Substance

logger = logging.getLogger("flamecheck.audit")

router = Router(tags=["substances"])

# Header row for the CSV import format (also used for the downloadable template).
CSV_HEADER = ["name", "synonyms", "formula", "ions", "pubchem_id", "wikipedia_link"]

#: Column separator for the import file, so multi-value cells (ions, synonyms)
#: may use ```` `,` ```` without needing CSV quoting.
FIELD_SEP = ";"


def _require_admin(request) -> None:
    """Raise unless the request user is an admin."""
    if not (getattr(request.user, "is_admin", False)):
        raise AuthenticationError(403, "Admin role required.")


def _canonical_ion(symbol: str) -> tuple[str, int, str]:
    """
    Canonicalize an ion symbol and derive its charge and kind.

    The symbol is the source of truth: it is normalized to the canonical form
    (see :mod:`substances.ions`) and the charge / kind are derived from it.
    Raises :class:`IonSymbolError` when the symbol is not a valid ion.
    """
    canonical = canonical_symbol(symbol)
    _formula, charge = parse_ion(canonical)
    kind = Ion.Kind.ANION if charge < 0 else Ion.Kind.CATION
    return canonical, charge, kind


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


# NOTE: the literal ``/substances/import-*`` and ``/substances/export-csv``
# routes must be registered before the ``/substances/{substance_id}`` routes,
# otherwise the parameterized route shadows them.
@router.get("/substances/import-template", response=None, operation_id="substance_import_template")
def substance_import_template(request):
    """
    Return a sample CSV showing the expected import format (admin only).

    Columns are separated by ``;`` and the multi-value cells (``ions``,
    ``synonyms``) are separated by ``,``, so a cell may hold commas without
    needing CSV quoting.
    """
    _require_admin(request)
    sample = "\n".join(
        [
            FIELD_SEP.join(CSV_HEADER),
            # name;synonyms;formula;ions;pubchem_id;wikipedia_link (6 columns)
            "Sodium chloride;Table salt;NaCl;Na+1,Cl-1;238914022;https://en.wikipedia.org/wiki/Sodium_chloride",
            "Potassium sulfate;;K2SO4;K+1,SO4-2;;",
        ]
    )
    return _csv_response(sample, filename="substances_import_template.csv")


@router.get("/substances/export-csv", response=None, operation_id="substance_export_csv")
def export_substances_csv(request):
    """
    Export the full substance catalog as a CSV in the import format (admin only).

    Columns are separated by ``;`` and the multi-value cells (``ions``,
    ``synonyms``) are separated by ``,``, so the file can be re-imported directly
    with the CSV import. The ``ions`` cell holds the ion symbols.
    """
    _require_admin(request)
    rows = [FIELD_SEP.join(CSV_HEADER)]
    for substance in Substance.objects.all().prefetch_related("ions"):
        rows.append(
            FIELD_SEP.join(
                [
                    substance.name,
                    ",".join(substance.synonyms or []),
                    substance.formula or "",
                    ",".join(ion.symbol for ion in substance.ions.all()),
                    substance.pubchem_id or "",
                    substance.wikipedia_link or "",
                ]
            )
        )
    return _csv_response("\n".join(rows) + "\n", filename="substances.csv")


@router.post("/substances/import-csv", response=ImportCsvOut)
def import_substances_csv(request, file: UploadedFile):
    """
    Import substances from an uploaded CSV file (admin only).

    Expected columns (first row is a header): ``name`` (required), ``synonyms``,
    ``formula``, ``ions`` (comma-separated ion symbols), ``pubchem_id``,
    ``wikipedia_link``. Columns are separated by ``;`` (a comma is also accepted
    as the column separator for compatibility). Substances are matched by name;
    a matching row updates the existing substance, otherwise a new one is
    created. Ion symbols are normalized to the canonical form (see
    :mod:`substances.ions`) and resolved against existing ions; symbols that
    are not found are collected in ``missing_ions`` unless the
    ``create_missing_ions`` form field is set to ``true``, in which case bare
    ions (charge and kind derived from the symbol) are created. Invalid symbols
    (no charge sign) are reported per line and skipped.
    """
    _require_admin(request)
    # ``create_missing_ions`` arrives as a multipart form field (or query param);
    # accept the common truthy spellings.
    raw_flag = request.POST.get("create_missing_ions") or request.GET.get("create_missing_ions") or ""
    create_missing_ions = str(raw_flag).strip().lower() in {"1", "true", "yes", "on"}
    raw = file.read()
    if not raw:
        raise ValidationError({"file": ["The uploaded file is empty."]})
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError({"file": [f"File is not valid UTF-8: {exc}"]}) from exc

    # The import file uses ``;`` as the column separator (so the ``ions`` cell
    # may hold commas); fall back to `,` for legacy comma-separated files.
    delim = FIELD_SEP if FIELD_SEP in text.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if reader.fieldnames is None or "name" not in [f.strip() for f in reader.fieldnames]:
        raise ValidationError({"file": ["CSV must have a header row with a 'name' column."]})

    created = updated = skipped = 0
    missing_ions: list[str] = []
    errors: list[str] = []
    seen_missing: set[str] = set()

    for line_no, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            skipped += 1
            errors.append(f"Line {line_no}: missing 'name' - skipped.")
            continue
        try:
            ion_ids: list[int] = []
            for symbol in _split_list(row.get("ions")):
                try:
                    symbol = canonical_symbol(symbol)
                except IonSymbolError as exc:
                    errors.append(f"Line {line_no}: invalid ion symbol {symbol!r} ({exc}) - skipped.")
                    continue
                ion = Ion.objects.filter(symbol=symbol).first()
                if ion is None:
                    if create_missing_ions:
                        ion = _create_ion_from_symbol(symbol)
                    else:
                        if symbol not in seen_missing:
                            seen_missing.add(symbol)
                            missing_ions.append(symbol)
                if ion is not None:
                    ion_ids.append(ion.id)
            substance = Substance.objects.filter(name=name).first()
            fields = {
                "synonyms": _split_list(row.get("synonyms")),
                "formula": (row.get("formula") or "").strip(),
                "pubchem_id": (row.get("pubchem_id") or "").strip(),
                "wikipedia_link": (row.get("wikipedia_link") or "").strip(),
            }
            if substance is None:
                substance = Substance.objects.create(name=name, **fields)
                if ion_ids:
                    substance.ions.set(ion_ids)
                created += 1
            else:
                for field, value in fields.items():
                    setattr(substance, field, value)
                substance.save()
                substance.ions.set(ion_ids)
                updated += 1
        except Exception as exc:
            errors.append(f"Line {line_no} ({name}): {exc}")

    total_rows = created + updated + skipped
    logger.info(
        "Admin %s imported substances CSV: %d created, %d updated, %d skipped, %d missing ions",
        request.user.username,
        created,
        updated,
        skipped,
        len(missing_ions),
    )
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_rows": total_rows,
        "missing_ions": sorted(missing_ions),
        "errors": errors[:50],
    }


@router.get("/substances/{substance_id}", response=SubstanceOut)
def get_substance(request, substance_id: int):
    """Return a single substance with its ion breakdown."""
    substance = Substance.objects.filter(pk=substance_id).prefetch_related("ions").first()
    if substance is None:
        raise HttpError(404, "Substance not found.")
    return substance_to_schema(substance)


@router.post("/ions", response=IonOut)
def create_ion(request, payload: IonIn):
    """
    Create a new ion (admin only).

    The ``symbol`` must be a valid ion and is stored in canonical form
    (``<formula><sign><magnitude>``); the ``charge`` and ``kind`` are derived
    from it, so any values sent for them are ignored.
    """
    _require_admin(request)
    try:
        symbol, charge, kind = _canonical_ion(payload.symbol)
    except IonSymbolError as exc:
        raise ValidationError({"symbol": [str(exc)]}) from exc
    ion = Ion.objects.create(symbol=symbol, name=payload.name, charge=charge, kind=kind, group=payload.group)
    return ion_to_schema(ion)


@router.put("/ions/{ion_id}", response=IonOut)
def update_ion(request, ion_id: int, payload: IonIn):
    """
    Update an ion (admin only).

    The ``symbol`` is canonicalized and the ``charge`` / ``kind`` are derived
    from it (see :func:`create_ion`).
    """
    _require_admin(request)
    try:
        symbol, charge, kind = _canonical_ion(payload.symbol)
    except IonSymbolError as exc:
        raise ValidationError({"symbol": [str(exc)]}) from exc
    ion = Ion.objects.get(pk=ion_id)
    ion.symbol = symbol
    ion.name = payload.name
    ion.charge = charge
    ion.kind = kind
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


# ---- CSV import -----------------------------------------------------------------
def _split_list(value: str | None) -> list[str]:
    """Split a delimited CSV cell (comma or semicolon) into a clean list."""
    if not value:
        return []
    parts = value.replace(";", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def _create_ion_from_symbol(symbol: str) -> Ion:
    """Create a bare ion from a symbol string (canonicalized; charge/kind derived)."""
    canonical, charge, kind = _canonical_ion(symbol)
    ion, _created = Ion.objects.get_or_create(
        symbol=canonical,
        kind=kind,
        defaults={"name": canonical, "charge": charge, "group": ""},
    )
    return ion


def _csv_response(body: str, filename: str) -> HttpResponse:
    """Build a ``text/csv`` attachment response with the given file name."""
    response = HttpResponse(body, content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
