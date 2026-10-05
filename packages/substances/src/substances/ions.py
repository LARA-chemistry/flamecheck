"""
Canonical ion symbol convention and parsing.

FlameCheck denotes an ion by a single *canonical* string::

    <formula><sign><magnitude>      e.g.  SO4-2   Na+1   NH4+1   Mg+2

* **formula** is everything before the charge sign: element symbols with
  plain-digit subscripts (optionally grouped in parentheses);
* **charge** is the substring from the *last* ``+``/``-`` to the end — a signed
  integer whose magnitude digit is *always* present (a unit charge is written
  ``+1``/``-1``, never a bare ``+``/``-``).

The charge is a trailing suffix and the formula never contains a ``+``/``-``
for standard inorganic ions, so splitting at the *last* sign is unambiguous
(even for multi-valent cations such as ``Fe+2``/``Fe+3``).

The parser is lenient in what it *accepts* (surrounding whitespace, Unicode
subscripts in the formula, and the IUPAC Unicode charge written as a superscript
in magnitude-then-sign order, ``SO₄²⁻``) but always *outputs* the canonical
ASCII form. See ``docs/development/ion_symbol_convention.md`` for the full spec.
"""

from __future__ import annotations

import re

# A *single* element symbol (one capital + optional lowercase) followed by a
# trailing digit, e.g. "Mg2" / "Fe3". With a bare sign this is the ambiguous
# legacy "digit-then-sign" form and is rejected (see the module docstring).
_SINGLE_ELEMENT_WITH_DIGIT = re.compile(r"[A-Z][a-z]?\d+\Z")

_SUB_DIGITS = "₀₁₂₃₄₅₆₇₈₉"
_SUP_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUP_SIGN = {"⁺": "+", "⁻": "-"}
_SUPER_CHARS = frozenset(_SUP_DIGITS + "⁺⁻")
_SUB_TRANS = str.maketrans(_SUB_DIGITS, "0123456789")
_SUP_D_TRANS = str.maketrans(_SUP_DIGITS, "0123456789")


class IonSymbolError(ValueError):
    """A string is not a valid ion symbol (no charge, malformed tail, ...)."""


def normalize(raw: str) -> str:
    """
    Normalize a human ion symbol to the canonical ASCII form.

    Accepts surrounding/internal whitespace, Unicode subscripts in the formula
    (``SO₄`` → ``SO4``) and the IUPAC Unicode charge (superscript
    magnitude-then-sign, ``SO₄²⁻`` → ``SO4-2``). Raises
    :class:`IonSymbolError` when the result is not a valid ion symbol.
    """
    s = "".join(raw.split())
    # Peel off the trailing run of superscript characters (the IUPAC charge).
    i = len(s)
    while i > 0 and s[i - 1] in _SUPER_CHARS:
        i -= 1
    formula_part = s[:i].translate(_SUB_TRANS)
    sup_charge = s[i:]

    if sup_charge:
        sign_char = next((ch for ch in sup_charge if ch in _SUP_SIGN), None)
        if sign_char is None:
            raise IonSymbolError(f"{raw!r}: the charge has no sign.")
        magnitude = "".join(ch for ch in sup_charge if ch in _SUP_DIGITS).translate(_SUP_D_TRANS)
        charge_str = _SUP_SIGN[sign_char] + (magnitude if magnitude.isdigit() else "1")
        formula = formula_part
    else:
        j = max(formula_part.rfind("+"), formula_part.rfind("-"))
        if j < 0:
            raise IonSymbolError(f"{raw!r}: not an ion (no charge sign).")
        head, sign, tail = formula_part[:j], formula_part[j], formula_part[j + 1 :]
        if tail and not tail.isdigit():
            raise IonSymbolError(f"{raw!r}: malformed charge {tail!r}.")
        if not tail and _SINGLE_ELEMENT_WITH_DIGIT.fullmatch(head):
            raise IonSymbolError(
                f"{raw!r} is ambiguous (legacy digit-then-sign); write the sign before the magnitude, e.g. 'Mg+2'."
            )
        formula = head
        charge_str = sign + (tail or "1")

    if not formula or not (formula[0].isalpha() or formula[0] == "("):
        raise IonSymbolError(f"{raw!r}: the formula must start with a letter.")
    return f"{formula}{charge_str}"


def parse_ion(symbol: str) -> tuple[str, int]:
    """
    Split an ion symbol into ``(formula, charge)``.

    The input is normalized first (see :func:`normalize`), so any of the
    accepted notations work. The charge is the signed integer after the last
    sign; the formula is everything before it.
    """
    s = normalize(symbol)
    i = max(s.rfind("+"), s.rfind("-"))
    sign, magnitude = s[i], int(s[i + 1 :])
    return s[:i], (magnitude if sign == "+" else -magnitude)


def canonical(formula: str, charge: int) -> str:
    """Build the canonical symbol ``<formula><sign><magnitude>`` from parts."""
    if charge == 0:
        raise IonSymbolError("a neutral species (charge 0) is not an ion.")
    return f"{formula}{'+' if charge > 0 else '-'}{abs(charge)}"


def canonical_symbol(symbol: str) -> str:
    """Return the canonical form of any valid ion-symbol input (e.g. ``'Mg²⁺'`` → ``'Mg+2'``)."""
    return normalize(symbol)
