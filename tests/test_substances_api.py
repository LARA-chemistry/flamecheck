"""Tests for the substances (ions/substances) API."""

import pytest
from substances.models import Ion, Substance

pytestmark = pytest.mark.django_db


@pytest.fixture
def populated(db, course):
    """Ensure a minimal ion/substance catalog exists (catalog may be empty in tests)."""
    cation, _ = Ion.objects.get_or_create(symbol="Pt+", name="Platinum", charge=1, kind="cation", group="Group VIII")
    anion, _ = Ion.objects.get_or_create(symbol="I-", name="Iodide", charge=-1, kind="anion", group="Halides")
    substance, _ = Substance.objects.get_or_create(name="Platinum iodide", formula="PtI")
    substance.ions.set([cation, anion])
    return cation, anion, substance


class TestReadEndpoints:
    def test_list_ions_requires_auth(self, client):
        assert client.get("/api/v1/ions").status_code == 401

    def test_list_ions_filtered(self, client, student, populated, auth_headers):
        cation, anion, _ = populated
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
