"""Tests for the canonical ion symbol convention (substances.ions)."""

from __future__ import annotations

import pytest
from substances.ions import (
    IonSymbolError,
    canonical,
    canonical_symbol,
    normalize,
    parse_ion,
)


class TestParseCanonical:
    """Canonical inputs (formula + sign + magnitude) parse directly."""

    @pytest.mark.parametrize(
        ("symbol", "formula", "charge"),
        [
            ("SO4-2", "SO4", -2),
            ("Mg+2", "Mg", 2),
            ("Na+1", "Na", 1),
            ("Cl-1", "Cl", -1),
            ("NH4+1", "NH4", 1),
            ("Fe+3", "Fe", 3),
            ("PO4-3", "PO4", -3),
            ("S-2", "S", -2),
            ("NO2-1", "NO2", -1),
        ],
    )
    def test_canonical(self, symbol: str, formula: str, charge: int) -> None:
        assert parse_ion(symbol) == (formula, charge)


class TestNormalization:
    """Non-canonical but valid inputs are normalized to canonical form."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # bare sign -> unit charge (digit added on storage)
            ("Na+", "Na+1"),
            ("Cl-", "Cl-1"),
            ("Ag+", "Ag+1"),
            # polyatomic with a subscript digit stays a unit charge
            ("NH4+", "NH4+1"),
            # Unicode IUPAC charge (superscript magnitude-then-sign)
            ("SO₄²⁻", "SO4-2"),
            ("Mg²⁺", "Mg+2"),
            ("Na⁺", "Na+1"),
            ("PO₄³⁻", "PO4-3"),
            ("NH₄⁺", "NH4+1"),
            # whitespace
            ("  Na + 1 ", "Na+1"),
            (" S O 4 - 2 ", "SO4-2"),
            # idempotent
            ("Mg+2", "Mg+2"),
            ("SO4-2", "SO4-2"),
        ],
    )
    def test_normalize(self, raw: str, expected: str) -> None:
        assert canonical_symbol(raw) == expected
        assert normalize(raw) == expected

    def test_parse_after_normalization(self) -> None:
        assert parse_ion("SO₄²⁻") == ("SO4", -2)
        assert parse_ion("Na+") == ("Na", 1)


class TestCanonicalFromParts:
    def test_build(self) -> None:
        assert canonical("SO4", -2) == "SO4-2"
        assert canonical("Mg", 2) == "Mg+2"
        assert canonical("Na", 1) == "Na+1"
        assert canonical("NH4", 1) == "NH4+1"

    def test_zero_charge_rejected(self) -> None:
        with pytest.raises(IonSymbolError):
            canonical("H2O", 0)


class TestRejection:
    """Invalid / ambiguous inputs are rejected with IonSymbolError."""

    @pytest.mark.parametrize(
        "raw",
        [
            "H2O",  # neutral, no charge sign
            "SO4",  # no charge sign
            "+",  # no formula
            "-",  # no formula
            "SO4-2x",  # malformed charge tail
            "2Na+1",  # leading coefficient
            "Mg2+",  # ambiguous legacy digit-then-sign
            "Fe3+",  # ambiguous legacy digit-then-sign
            "Mn2-",  # ambiguous legacy digit-then-sign (anion)
        ],
    )
    def test_rejects(self, raw: str) -> None:
        with pytest.raises(IonSymbolError):
            normalize(raw)

    def test_rejection_message_mentions_canonical(self) -> None:
        with pytest.raises(IonSymbolError, match="Mg\\+2"):
            normalize("Mg2+")


class TestRoundTrip:
    def test_catalog_symbols_are_canonical(self) -> None:
        # Every symbol in the demo catalog must already be in canonical form.
        from substances.factory import ION_CATALOG

        for symbol in (value[0] for value in ION_CATALOG.values()):
            assert canonical_symbol(symbol) == symbol, symbol
