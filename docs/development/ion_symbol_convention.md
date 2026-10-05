# Ion Symbol Convention

FlameCheck stores and exchanges ions as a single **canonical string**. This page
defines that convention, the rules the parser applies to human input, and the
IUPAC display form used in the UI. It is the authoritative reference for the
`Ion.symbol` field and for every place an ion symbol is written (factories,
data fixtures, the CSV import, the API, and the tests).

## 1. The canonical string form

An ion symbol is

```text
<formula><sign><magnitude>
```

where

| Part        | Rule                                                                                  |
| ----------- | ------------------------------------------------------------------------------------- |
| `formula`   | Element symbols with plain-digit subscripts, optionally grouped in parentheses. It never contains a `+` or `-`. e.g. `Na`, `NH4`, `SO4`, `Cr(H2O)6`. |
| `sign`      | A single `+` (cation) or `-` (anion), placed **immediately after** the formula.        |
| `magnitude` | A positive integer. The digit is **always present**, including for a unit charge — so a +1 ion is `Na+1`, never `Na+`. |

Examples:

```text
Na+1    K+1     NH4+1   Mg+2    Fe+3    SO4-2   PO4-3   Cl-1    NO2-1   S-2
```

### Why this ordering

The charge is a **trailing suffix** and the formula never contains a sign, so the
charge is unambiguously the substring from the **last** `+`/`-` to the end of the
string. This holds for every standard inorganic ion and, crucially, disambiguates
multi-valent cations: `Fe+2` (iron(II)) and `Fe+3` (iron(III)) are two distinct,
self-describing symbols.

The legacy ordering that put the magnitude *before* the sign (`Mg2+`) is
ambiguous with a formula that ends in a subscript digit (`NH4+` is ammonium, not
"NH⁴⁺"), so it is **not** accepted as input (see §4 and §6).

## 2. What the parser accepts

The parser (`substances.ions`) is *lenient in what it accepts* but *always
outputs the canonical form*. It normalizes the following real-world variants to
canonical ASCII before validating:

- **Surrounding / internal whitespace** — ` Na + 1 ` → `Na+1`.
- **Unicode subscripts in the formula** — `SO₄` → `SO4`.
- **The IUPAC Unicode charge** (superscript, magnitude-then-sign) —
  `SO₄²⁻` → `SO4-2`, `Mg²⁺` → `Mg+2`, `Na⁺` → `Na+1`.

After normalization the symbol is validated:

1. There must be a charge sign with a non-empty formula before it.
2. Everything after the sign must be a (possibly empty) run of digits; an empty
   run is a unit charge. A non-digit tail is rejected.
3. The formula must start with a letter (a leading coefficient such as `2Na+` is
   rejected).

A string that is not an ion (no charge sign, e.g. `H2O`) or a malformed charge
raises `IonSymbolError`.

### Normalization examples

| Input          | Canonical | Notes                              |
| -------------- | --------- | ---------------------------------- |
| `SO4-2`        | `SO4-2`   | already canonical                  |
| `Na+`          | `Na+1`    | bare sign → unit charge            |
| `Mg+2`         | `Mg+2`    | canonical                          |
| `SO₄²⁻`        | `SO4-2`   | Unicode charge, re-ordered         |
| `Mg²⁺`         | `Mg+2`    | Unicode charge                     |
| ` NH4 + 1 `    | `NH4+1`   | whitespace stripped                |
| `Na+1`         | `Na+1`    | idempotent                         |

## 3. IUPAC display form (UI rendering)

The UI renders ions with proper sub-/superscripts, following the IUPAC
recommendation that the charge magnitude precedes the sign in the superscript and
that the `1` is omitted for a unit charge:

| Canonical | Rendered | Superscript rule            |
| --------- | -------- | --------------------------- |
| `SO4-2`   | SO₄²⁻    | `2` then `−`               |
| `PO4-3`   | PO₄³⁻    | `3` then `−`               |
| `Mg+2`    | Mg²⁺     | `2` then `+`               |
| `Fe+3`    | Fe³⁺     | `3` then `+`               |
| `Na+1`    | Na⁺      | unit → sign only           |
| `Cl-1`    | Cl⁻      | unit → sign only           |
| `NH4+1`   | NH₄⁺     | unit → sign only           |

Formula digits are rendered as subscripts (`SO4` → SO₄). The reusable
`IonSymbol` component (frontend) applies this rule; it is used on the submission
ion list, the confirmation dialog, the result breakdown, and the student profile.

## 4. Enforcement

The canonical form is **enforced on human input** at every entry point:

- **Ion create / update API** (`POST/PUT /api/v1/ions`) — the `symbol` is
  normalized to canonical form and the `charge` / `kind` are *derived* from it
  (the `charge` and `kind` sent in the payload are ignored). An invalid symbol
  returns a `422` with a clear message.
- **Substance CSV import** (`POST /api/v1/substances/import-csv`) — each ion
  symbol in the `ions` cell is canonicalized before it is resolved against the
  catalog; unknown canonical symbols are reported in `missing_ions` (or created
  when `create_missing_ions` is set), and invalid symbols are reported per line.
- **Model help text** — `Ion.symbol` documents the canonical form.

Because the stored `symbol` is always canonical, the `charge` integer and the
`kind` (cation/anion) are redundant with it and are kept consistent by deriving
them from the symbol.

## 5. Migration from the legacy forms

The repository previously mixed three notations. The one-time migration mapped
them to canonical form (this table is the complete mapping):

| Legacy            | Canonical | Legacy meaning      |
| ----------------- | --------- | ------------------- |
| `Na+` / `K+` / `NH4+` / `Pt+` / `Ag+` | `Na+1` / `K+1` / `NH4+1` / `Pt+1` / `Ag+1` | unit cations |
| `Mg2+` `Ca2+` `Ba2+` `Cu2+` `Zn2+` `Mn2+` | `Mg+2` `Ca+2` `Ba+2` `Cu+2` `Zn+2` `Mn+2` | divalent cations |
| `Fe2+` / `Fe3+` / `Al3+` | `Fe+2` / `Fe+3` / `Al+3` | multi-valent cations |
| `Cl-` / `Br-` / `I-` / `NO3-` | `Cl-1` / `Br-1` / `I-1` / `NO3-1` | unit anions |
| `S2-`             | `S-2`     | data bug — sodium sulfide is the sulfide anion S²⁻, not the disulfide S₂⁻ |
| `SO4^2-` (caret)  | `SO4-2`   | caret charge notation (help text / docstrings) |

Already-canonical symbols (`SO4-2`, `SO3-2`, `CO3-2`, `PO4-3`, `NO3-1`, `NO2-1`,
`S-2`) were left unchanged.

## 6. Borderline cases

| Case                          | Handling                                                             |
| ----------------------------- | -------------------------------------------------------------------- |
| Unit charge, bare sign (`Na+`) | Accepted and normalized to `Na+1` (the digit is added on storage).   |
| Formula ends in a digit (`NH4+`) | Treated as the polyatomic ammonium (`NH4+1`), not a charge. The trailing-sign rule means the `4` stays in the formula. |
| Legacy digit-then-sign (`Mg2+`) | **Rejected** as non-canonical — the human must send `Mg+2`. (The migration mapped the existing data explicitly.) |
| Neutral species (`H2O`)       | Rejected — no charge sign, not an ion.                               |
| Leading coefficient (`2Na+`)  | Rejected — the formula must start with a letter.                     |
| Malformed tail (`SO4-2x`)     | Rejected — the charge tail must be digits.                           |
| Unicode IUPAC (`SO₄²⁻`)       | Accepted and re-ordered to `SO4-2`.                                  |

## 7. Reference implementation

- **Parser / normalization** — `packages/substances/src/substances/ions.py`
  (`normalize`, `parse_ion`, `canonical`, `canonical_symbol`, `IonSymbolError`).
- **API enforcement** — `packages/substances/src/substances/api/views.py`
  (`_canonical_ion`, `create_ion`, `update_ion`, the CSV import loop).
- **Catalog** — `ION_CATALOG` in `packages/substances/src/substances/factory.py`
  and `packages/substances/data/ions.json` (both canonical).
- **UI rendering** — `frontend/src/utils/ion.js` + `frontend/src/components/IonSymbol.vue`.
