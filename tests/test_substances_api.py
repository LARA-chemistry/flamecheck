"""Tests for the substances (ions/substances) API."""

import pytest
from substances.factory import IonFactory, SubstanceFactory
from substances.models import Ion, Substance

pytestmark = pytest.mark.django_db


@pytest.fixture
def populated(db, course):
    """Ensure a minimal ion/substance catalog exists (catalog may be empty in tests)."""
    # Unique symbols (not in the factory catalog) so this fixture is isolated
    # from the shared `ions` fixture and the admin-create test (which uses Ag+1).
    cation = IonFactory(symbol="Pt+1", name="Platinum", charge=1, kind="cation", group="Group VIII")
    anion = IonFactory(symbol="I-1", name="Iodide", charge=-1, kind="anion", group="Halides")
    substance = SubstanceFactory(name="Platinum iodide", formula="PtI", ions=[cation, anion])
    return cation, anion, substance


class TestReadEndpoints:
    def test_list_ions_requires_auth(self, client):
        assert client.get("/api/v1/ions").status_code == 401

    def test_list_ions_filtered(self, client, student, populated, auth_headers):
        cation, _anion, _substance = populated
        resp = client.get("/api/v1/ions", **auth_headers(student))
        assert resp.status_code == 200
        symbols = {i["symbol"] for i in resp.json()}
        assert cation.symbol in symbols
        resp = client.get("/api/v1/ions?kind=cation", **auth_headers(student))
        assert all(i["kind"] == "cation" for i in resp.json())

    def test_get_ion(self, client, student, populated, auth_headers):
        cation, _, _ = populated
        resp = client.get(f"/api/v1/ions/{cation.id}", **auth_headers(student))
        assert resp.status_code == 200
        assert resp.json()["symbol"] == cation.symbol

    def test_list_substances_with_ions(self, client, student, populated, auth_headers):
        _, _, substance = populated
        resp = client.get(f"/api/v1/substances/{substance.id}", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        assert data["formula"] == "PtI"
        assert {i["symbol"] for i in data["ions"]} == {"Pt+1", "I-1"}

    def test_substance_exposes_pubchem_url(self, client, student, populated, auth_headers):
        """The substance payload carries a PubChem page URL built from the setting."""
        from django.conf import settings

        _, _, substance = populated
        substance.pubchem_id = "238914022"
        substance.save(update_fields=["pubchem_id"])
        resp = client.get(f"/api/v1/substances/{substance.id}", **auth_headers(student))
        assert resp.status_code == 200
        data = resp.json()
        assert data["pubchem_url"] == f"{settings.PUBCHEM_BASE_URL.rstrip('/')}/238914022"

    def test_substance_pubchem_url_none_without_cid(self, client, student, auth_headers):
        """A substance without a PubChem CID has a null pubchem_url."""
        substance = SubstanceFactory(name="No CID salt", pubchem_id="")
        resp = client.get(f"/api/v1/substances/{substance.id}", **auth_headers(student))
        assert resp.status_code == 200
        assert resp.json()["pubchem_url"] is None


class TestPubChemUrl:
    """The reusable Substance.pubchem_url helper (settings-driven base)."""

    def test_builds_url_from_setting(self, db):
        from django.conf import settings

        substance = SubstanceFactory(pubchem_id="111")
        assert substance.pubchem_url == f"{settings.PUBCHEM_BASE_URL.rstrip('/')}/111"

    def test_none_when_no_cid(self, db):
        substance = SubstanceFactory(pubchem_id="")
        assert substance.pubchem_url is None

    def test_ignores_trailing_slash_in_setting(self, db, settings):
        settings.PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/compound/"
        substance = SubstanceFactory(pubchem_id="222")
        assert substance.pubchem_url == "https://pubchem.ncbi.nlm.nih.gov/compound/222"


class TestAdminMutations:
    def test_student_cannot_create_ion(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Ag+1", "name": "Silver", "charge": 1, "kind": "cation", "group": "Group I"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_admin_creates_ion(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Ag+1", "name": "Silver", "charge": 1, "kind": "cation", "group": "Group I"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert Ion.objects.filter(symbol="Ag+1").exists()

    def test_create_ion_canonicalizes_bare_symbol(self, client, admin_user, auth_headers):
        # A bare-sign input is normalized to the canonical form (digit added).
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Ag+", "name": "Silver", "kind": "cation"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "Ag+1"
        assert body["charge"] == 1
        assert body["kind"] == "cation"

    def test_create_ion_derives_charge_and_kind_from_symbol(self, client, admin_user, auth_headers):
        # The symbol is authoritative: sent charge/kind are ignored.
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Xx+2", "name": "Xenon-like", "charge": 1, "kind": "cation"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "Xx+2"
        assert body["charge"] == 2
        assert body["kind"] == "cation"

    def test_create_ion_derives_anion(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Se-2", "name": "Selenide", "charge": 0, "kind": "cation"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "Se-2"
        assert body["charge"] == -2
        assert body["kind"] == "anion"

    def test_create_ion_rejects_non_ion_symbol(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "H2O", "name": "Water", "kind": "cation"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422
        assert not Ion.objects.filter(symbol="H2O").exists()

    def test_create_ion_rejects_legacy_digit_then_sign(self, client, admin_user, auth_headers):
        # The ambiguous legacy form is rejected; the canonical form is required.
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Mg2+", "name": "Magnesium", "kind": "cation"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422
        assert not Ion.objects.filter(symbol="Mg2+").exists()

    def test_admin_updates_substance(self, client, admin_user, populated, auth_headers):
        cation, _, substance = populated
        resp = client.put(
            f"/api/v1/substances/{substance.id}",
            {
                "name": "Sodium chloride (table salt)",
                "formula": "NaCl",
                "ion_ids": [cation.id],
            },
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        substance.refresh_from_db()
        assert substance.name == "Sodium chloride (table salt)"
        assert list(substance.ions.all()) == [cation]

    def test_admin_cannot_delete_referenced_ion(self, client, admin_user, populated, assigned_instance, auth_headers):
        cation, _, _ = populated
        if assigned_instance.type.possible_ions.filter(pk=cation.id).exists():
            resp = client.delete(f"/api/v1/ions/{cation.id}", **auth_headers(admin_user))
            assert resp.status_code == 400
            assert Ion.objects.filter(pk=cation.id).exists()


class TestCsvImport:
    """Tests for the admin-only CSV import endpoint."""

    @staticmethod
    def _csv_upload(csv_text: str):
        """Build a multipart file upload payload from CSV text."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile("substances.csv", csv_text.encode("utf-8"), content_type="text/csv")

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload("name,formula\nX,Y")},
        )
        assert resp.status_code == 401

    def test_forbidden_for_non_admin(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload("name,formula\nX,Y")},
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_import_creates_and_updates(self, client, admin_user, populated, auth_headers):
        cation, anion, existing = populated
        # Columns are ``;``-separated; the ions cell is comma-separated.
        csv_text = (
            "name;synonyms;formula;ions;pubchem_id;wikipedia_link\n"
            f"Fresh salt;Allosalt;KI;{cation.symbol},{anion.symbol};;;\n"
            f"{existing.name};Updated alias;KI;{cation.symbol},{anion.symbol};123;https://en.wiki/I\n"
        )
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload(csv_text)},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["created"] == 1
        assert data["updated"] == 1
        fresh = Substance.objects.get(name="Fresh salt")
        assert fresh.formula == "KI"
        assert set(fresh.ions.values_list("symbol", flat=True)) == {cation.symbol, anion.symbol}
        # The pre-existing substance was updated, not duplicated.
        assert Substance.objects.filter(name=existing.name).count() == 1
        updated = Substance.objects.get(pk=existing.id)
        assert updated.synonyms == ["Updated alias"]
        assert set(updated.ions.values_list("symbol", flat=True)) == {cation.symbol, anion.symbol}

    def test_missing_ions_collected(self, client, admin_user, auth_headers):
        csv_text = "name;formula;ions\nMystery salt;??;Zz+,Qq-\n"
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload(csv_text)},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["missing_ions"]) == {"Zz+1", "Qq-1"}
        assert data["created"] == 1
        # No ions were auto-created (the bare tokens canonicalize to Zz+1 / Qq-1).
        assert not Ion.objects.filter(symbol="Zz+1").exists()

    def test_comma_separated_columns_still_accepted(self, client, admin_user, auth_headers):
        # Legacy comma-separated files (ions cell quoted) still parse.
        csv_text = 'name,formula,ions\nQuoted salt,??,"Zz+,Qq-"\n'
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload(csv_text)},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["missing_ions"]) == {"Zz+1", "Qq-1"}
        assert data["created"] == 1

    def test_create_missing_ions(self, client, admin_user, auth_headers):
        csv_text = "name;formula;ions\nMystery salt;??;Zz+,Qq-\n"
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload(csv_text), "create_missing_ions": "true"},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["missing_ions"] == []
        assert Ion.objects.get(symbol="Zz+1").kind == Ion.Kind.CATION
        assert Ion.objects.get(symbol="Qq-1").kind == Ion.Kind.ANION

    def test_rejects_empty_file(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload("")},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_rejects_missing_name_column(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload("formula,name_missing\nNaCl,x")},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 422

    def test_rows_without_name_are_skipped(self, client, admin_user, populated, auth_headers):
        cation, _, _ = populated
        csv_text = f"name;ions\n;\n\nGood salt;{cation.symbol}\n"
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload(csv_text)},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] >= 1
        assert any("name" in e for e in data["errors"])

    def test_template_download(self, client, admin_user, auth_headers):
        resp = client.get("/api/v1/substances/import-template", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        lines = resp.content.decode().strip().splitlines()
        assert lines[0] == "name;synonyms;formula;ions;pubchem_id;wikipedia_link"
        # Each sample row has 6 ``;``-separated columns.
        assert all(len(line.split(";")) == 6 for line in lines)
        # The ions cell uses commas as the intra-cell separator (canonical symbols).
        assert "Na+1,Cl-1" in lines[1]

    def test_template_forbidden_for_student(self, client, student, auth_headers):
        resp = client.get("/api/v1/substances/import-template", **auth_headers(student))
        assert resp.status_code == 403


class TestCsvExport:
    """Tests for the admin-only CSV export endpoint."""

    @staticmethod
    def _csv_upload(csv_text: str):
        """Build a multipart file upload payload from CSV text."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile("substances.csv", csv_text.encode("utf-8"), content_type="text/csv")

    def test_export_format(self, client, admin_user, populated, auth_headers):
        cation, anion, substance = populated
        resp = client.get("/api/v1/substances/export-csv", **auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        assert "substances.csv" in resp["Content-Disposition"]
        lines = resp.content.decode().strip().splitlines()
        # Header plus one row for the populated substance.
        assert lines[0] == "name;synonyms;formula;ions;pubchem_id;wikipedia_link"
        assert len(lines) == 2
        # Every row has 6 ``;``-separated columns.
        assert all(len(line.split(";")) == 6 for line in lines)
        name, synonyms, formula, ions_cell, pubchem, wiki = lines[1].split(";")
        assert name == substance.name
        assert formula == substance.formula
        # The ions cell lists the ion symbols, comma-separated.
        assert set(ions_cell.split(",")) == {cation.symbol, anion.symbol}
        # The remaining cells round-trip the substance's own field values.
        assert synonyms == ",".join(substance.synonyms)
        assert pubchem == substance.pubchem_id
        assert wiki == substance.wikipedia_link

    def test_export_round_trip(self, client, admin_user, populated, auth_headers):
        existing = populated[2]
        exported = client.get("/api/v1/substances/export-csv", **auth_headers(admin_user)).content.decode()
        # Re-importing the exported file matches by name and updates (no duplicate).
        resp = client.post(
            "/api/v1/substances/import-csv",
            {"file": self._csv_upload(exported)},
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["created"] == 0
        assert data["updated"] == 1
        assert data["missing_ions"] == []
        assert Substance.objects.filter(name=existing.name).count() == 1

    def test_export_empty_catalog(self, client, admin_user, auth_headers):
        resp = client.get("/api/v1/substances/export-csv", **auth_headers(admin_user))
        assert resp.status_code == 200
        lines = resp.content.decode().strip().splitlines()
        # Only the header row when no substance exists.
        assert lines == ["name;synonyms;formula;ions;pubchem_id;wikipedia_link"]

    def test_export_forbidden_for_student(self, client, student, auth_headers):
        resp = client.get("/api/v1/substances/export-csv", **auth_headers(student))
        assert resp.status_code == 403
