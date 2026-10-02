"""Tests for the substances (ions/substances) API."""

import pytest
from substances.factory import IonFactory, SubstanceFactory
from substances.models import Ion, Substance

pytestmark = pytest.mark.django_db


@pytest.fixture
def populated(db, course):
    """Ensure a minimal ion/substance catalog exists (catalog may be empty in tests)."""
    # Unique symbols (not in the factory catalog) so this fixture is isolated
    # from the shared `ions` fixture and the admin-create test (which uses Ag+).
    cation = IonFactory(symbol="Pt+", name="Platinum", charge=1, kind="cation", group="Group VIII")
    anion = IonFactory(symbol="I-", name="Iodide", charge=-1, kind="anion", group="Halides")
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
        assert {i["symbol"] for i in data["ions"]} == {"Pt+", "I-"}


class TestAdminMutations:
    def test_student_cannot_create_ion(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Ag+", "name": "Silver", "charge": 1, "kind": "cation", "group": "Group I"},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_admin_creates_ion(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/ions",
            {"symbol": "Ag+", "name": "Silver", "charge": 1, "kind": "cation", "group": "Group I"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert Ion.objects.filter(symbol="Ag+").exists()

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
        assert set(data["missing_ions"]) == {"Zz+", "Qq-"}
        assert data["created"] == 1
        # No ions were auto-created.
        assert not Ion.objects.filter(symbol="Zz+").exists()

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
        assert set(data["missing_ions"]) == {"Zz+", "Qq-"}
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
        assert Ion.objects.get(symbol="Zz+").kind == Ion.Kind.CATION
        assert Ion.objects.get(symbol="Qq-").kind == Ion.Kind.ANION

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
        # The ions cell uses commas as the intra-cell separator.
        assert "Na+,Cl-" in lines[1]

    def test_template_forbidden_for_student(self, client, student, auth_headers):
        resp = client.get("/api/v1/substances/import-template", **auth_headers(student))
        assert resp.status_code == 403
