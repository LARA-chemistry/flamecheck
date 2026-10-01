"""Tests for the random substance-assignment service and its admin endpoint."""

from __future__ import annotations

import random

import pytest
from analyses.factory import AnalysisInstanceFactory, AnalysisTypeFactory
from analyses.models import AnalysisInstance, AnalysisType
from analyses.services import (
    InsufficientIonsError,
    _pick_random_ion_subset,
    randomize_substances_for_announcement,
)
from config.factory import CourseFactory
from config.models import Course
from substances.factory import SubstanceFactory, create_ion_catalog
from users.factory import StudentAssignmentFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog_ions() -> list:
    """A 6-cation / 4-anion ion catalog."""
    return create_ion_catalog(
        [
            "sodium",
            "potassium",
            "ammonium",
            "magnesium",
            "calcium",
            "copper",
            "chloride",
            "bromide",
            "sulfate",
            "carbonate",
        ]
    )


@pytest.fixture
def analysis_type(catalog_ions) -> AnalysisType:
    """An analysis type whose possible set is the whole catalog."""
    return AnalysisTypeFactory(name="Random Test Analysis", possible_ions=catalog_ions)


@pytest.fixture
def course(db) -> Course:
    return CourseFactory(name="Random Test Course", is_active=True)


def _build_student_instances(analysis_type, course, number, count):
    """Create ``count`` per-student instances + assignments for the announcement."""
    instances = []
    for _ in range(count):
        student = UserFactory.create(role="student", name=f"Student {len(instances)}")
        inst = AnalysisInstanceFactory(
            type=analysis_type,
            course=course,
            number=number,
            correct_ions=[],
        )
        StudentAssignmentFactory(student=student, instance=inst, course=course, number=number)
        instances.append(inst)
    return instances


class TestPickRandomIonSubset:
    def test_size_within_bounds(self, catalog_ions):
        rng = random.Random(42)
        possible = catalog_ions
        for _ in range(50):
            ids = _pick_random_ion_subset(possible, 3, 5, rng)
            assert 3 <= len(ids) <= 5

    def test_mixes_cations_and_anions(self, catalog_ions):
        rng = random.Random(7)
        possible = catalog_ions
        mixed = 0
        for _ in range(50):
            ids = set(_pick_random_ion_subset(possible, 3, 5, rng))
            if any(i.kind == "cation" for i in possible if i.id in ids) and any(
                i.kind == "anion" for i in possible if i.id in ids
            ):
                mixed += 1
        assert mixed > 0

    def test_respects_small_pool(self, catalog_ions):
        rng = random.Random(1)
        small = catalog_ions[:2]  # only 2 ions
        ids = _pick_random_ion_subset(small, 3, 5, rng)
        assert len(ids) <= 2
        assert set(ids) == {i.id for i in small}


class TestRandomizeService:
    def test_randomizes_each_student(self, analysis_type, course, catalog_ions):
        instances = _build_student_instances(analysis_type, course, 1, 4)
        results = randomize_substances_for_announcement(course, 1, min_ions=3, max_ions=5, rng=random.Random(3))
        assert len(results) == 4
        for r, inst in zip(results, instances, strict=True):
            inst.refresh_from_db()
            assert 3 <= inst.correct_ions.count() <= 5
            # Every chosen ion must be from the type's possible set.
            possible_ids = set(analysis_type.possible_ions.values_list("id", flat=True))
            assert set(inst.correct_ions.values_list("id", flat=True)) <= possible_ids
            # assigned_substances are recorded.
            assert set(r.assigned_substance_ids) == set(inst.assigned_substances.values_list("id", flat=True))

    def test_assigned_substances_share_a_correct_ion(self, analysis_type, course, catalog_ions):
        # Give the catalog a couple of substances so the assignment is non-trivial.
        na, cl, k = catalog_ions[0], catalog_ions[6], catalog_ions[1]
        SubstanceFactory(name="Sodium chloride", ions=[na, cl])
        SubstanceFactory(name="Potassium chloride", ions=[k, cl])
        _build_student_instances(analysis_type, course, 2, 1)
        results = randomize_substances_for_announcement(course, 2, min_ions=3, max_ions=5, rng=random.Random(9))
        inst = results[0]
        instance = AnalysisInstance.objects.get(pk=inst.instance_id)
        correct_ids = set(instance.correct_ions.values_list("id", flat=True))
        for sub in instance.assigned_substances.all():
            # Each assigned substance shares at least one correct ion.
            assert set(sub.ions.values_list("id", flat=True)) & correct_ids

    def test_seeded_rng_is_deterministic(self, analysis_type, course, catalog_ions):
        instances_a = _build_student_instances(analysis_type, course, 1, 3)
        results_a = randomize_substances_for_announcement(course, 1, rng=random.Random(123))
        # Reset correct sets and re-run with the same seed on fresh instances.
        for inst in instances_a:
            inst.correct_ions.clear()
            inst.assigned_substances.clear()
        results_b = randomize_substances_for_announcement(course, 1, rng=random.Random(123))
        assert [r.correct_ion_ids for r in results_a] == [r.correct_ion_ids for r in results_b]

    def test_insufficient_ions_raises(self, catalog_ions, course):
        # A type with only 2 possible ions, but min_ions=3.
        small_type = AnalysisTypeFactory(name="Tiny", possible_ions=catalog_ions[:2])
        _build_student_instances(small_type, course, 5, 1)
        with pytest.raises(InsufficientIonsError):
            randomize_substances_for_announcement(course, 5, min_ions=3, max_ions=5, rng=random.Random(0))

    def test_no_instances_returns_empty(self, course):
        assert randomize_substances_for_announcement(course, 99, rng=random.Random(0)) == []


class TestRandomizeEndpoint:
    def _payload(self, course, number=1):
        return {"course_id": course.id, "number": number, "min_ions": 3, "max_ions": 5}

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/v1/admin/analysis-instances/randomize-substances",
            {"course_id": 1, "number": 1},
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_forbidden_for_student(self, client, student, auth_headers):
        resp = client.post(
            "/api/v1/admin/analysis-instances/randomize-substances",
            {"course_id": 1, "number": 1},
            content_type="application/json",
            **auth_headers(student),
        )
        assert resp.status_code == 403

    def test_admin_randomizes(self, client, admin_user, analysis_type, course, auth_headers):
        _build_student_instances(analysis_type, course, 3, 3)
        resp = client.post(
            "/api/v1/admin/analysis-instances/randomize-substances",
            self._payload(course, 3),
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["randomized"] == 3
        assert len(data["students"]) == 3
        for s in data["students"]:
            assert 3 <= len(s["correct_ions"]) <= 5
            assert all(ion["symbol"] for ion in s["correct_ions"])
        # The instances' correct_ions were actually updated.
        for inst in AnalysisInstance.objects.filter(course=course, number=3):
            assert inst.correct_ions.count() >= 1

    def test_404_unknown_course(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/admin/analysis-instances/randomize-substances",
            {"course_id": 99999, "number": 1},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_404_no_instances(self, client, admin_user, course, auth_headers):
        resp = client.post(
            "/api/v1/admin/analysis-instances/randomize-substances",
            {"course_id": course.id, "number": 42},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_400_insufficient_ions(self, client, admin_user, catalog_ions, course, auth_headers):
        small_type = AnalysisTypeFactory(name="Tiny EP", possible_ions=catalog_ions[:2])
        _build_student_instances(small_type, course, 7, 1)
        resp = client.post(
            "/api/v1/admin/analysis-instances/randomize-substances",
            {"course_id": course.id, "number": 7, "min_ions": 4, "max_ions": 6},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 400
