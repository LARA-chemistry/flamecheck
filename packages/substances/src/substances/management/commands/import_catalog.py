"""Import the ion and substance catalogs from CSV or JSON files."""

import csv
import json
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from substances.models import Ion, Substance

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _rows_from(path: Path, key: str) -> list[dict]:
    """Load rows from a JSON (with ``key``) or CSV (dict rows) catalog file."""
    if path.suffix == ".json":
        return _load_json(path).get(key, [])
    return _load_csv(path)


class Command(BaseCommand):
    """
    Import ions and substances from JSON/CSV catalogs.

    By default reads ``ions.json`` / ``ions.csv`` and ``substances.json`` /
    ``substances.csv`` from ``settings.CATALOG_DIR``. Existing ions are
    matched by (symbol, kind); existing substances by name.
    """

    help = "Import the ion and substance catalogs from the CATALOG_DIR."

    def add_arguments(self, parser):
        parser.add_argument("--dir", type=Path, default=None, help="Catalog directory (default: settings.CATALOG_DIR).")

    def handle(self, *args, **options):
        catalog_dir: Path = options["dir"] or Path(settings.CATALOG_DIR)
        self.import_ions(catalog_dir)
        self.import_substances(catalog_dir)
        self.stdout.write(self.style.SUCCESS(f"Ion catalog: {Ion.objects.count()} ions"))
        self.stdout.write(self.style.SUCCESS(f"Substance catalog: {Substance.objects.count()} substances"))

    def import_ions(self, catalog_dir: Path) -> int:
        """Import ions; returns the number of ions created."""
        rows = self._first(catalog_dir, ["ions.json", "ions.csv"], "ions")
        created = 0
        for row in rows:
            defaults = {
                "name": row.get("name", ""),
                "charge": int(row.get("charge", 0) or 0),
                "group": row.get("group", "") or "",
            }
            ion, was_created = Ion.objects.get_or_create(
                symbol=row["symbol"],
                kind=row["kind"],
                defaults=defaults,
            )
            if not was_created:
                changed = False
                for field, value in defaults.items():
                    if getattr(ion, field) != value:
                        setattr(ion, field, value)
                        changed = True
                if changed:
                    ion.save()
            else:
                created += 1
        return created

    def import_substances(self, catalog_dir: Path) -> int:
        """Import substances (resolving ion symbols to Ion rows); returns count created."""
        rows = self._first(catalog_dir, ["substances.json", "substances.csv"], "substances")
        created = 0
        for row in rows:
            ion_ids = []
            for symbol in row.get("ions", []) or []:
                ion = Ion.objects.filter(symbol=symbol).first()
                if ion is not None:
                    ion_ids.append(ion.id)
            defaults = {
                "synonyms": row.get("synonyms", []) or [],
                "formula": row.get("formula", "") or "",
                "pubchem_id": row.get("pubchem_id", "") or "",
                "wikipedia_link": row.get("wikipedia_link", "") or "",
            }
            substance, was_created = Substance.objects.get_or_create(name=row["name"], defaults=defaults)
            if ion_ids:
                substance.ions.set(ion_ids)
            if was_created:
                created += 1
        return created

    @staticmethod
    def _first(catalog_dir: Path, candidates: list[str], key: str) -> list[dict]:
        for name in candidates:
            path = catalog_dir / name
            if path.exists():
                return _rows_from(path, key)
        return []
