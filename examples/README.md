# FlameCheck example dataset

A complete, ready-to-use demo environment for the whole app: three courses
(two active), 11 users (admin, 2 assistants, 8 students with barcodes), four
analysis types, per-student analysis sheets in **open / too-early / too-late**
time windows, 28 assignments and a few pre-seeded, already-graded submissions.

## Files

| File | Content |
|---|---|
| `datasets/courses.json` | 3 courses (Biology active, Pharmacy active, Materials inactive) |
| `datasets/users.json` | admin + 2 assistants + 8 students (passwords, matriculation numbers, barcodes, course enrollment) |
| `datasets/assistant_courses.json` | which assistant supports which course |
| `datasets/analysis_types.json` | 4 analysis types, each with its *possible* ion set (ion symbols from the catalog) |
| `datasets/analysis_instances.json` | announcement templates per course: correct ion set + time window **as minute offsets from load time** |
| `datasets/assignments.json` | which students are assigned to which announcements (course × students × numbers) |
| `datasets/submissions.json` | pre-seeded submissions (created through the real, scoring `AnalysisInstance.submit()` logic) |
| `datasets/grading_config.json` | singleton grading configuration |
| `datasets/app_settings.json` | singleton app settings (active course, analyses per course) |
| `verify_demo.py` | end-to-end checker over live HTTP (54 checks: frontend, auth, student, assistant, admin, catalog, RBAC) |

The loader lives in the `analyses` app: `manage.py load_examples`.

## Design note: one sheet per student

An `AnalysisInstance` is one *sheet*, and its submission counters (the
3-submission limit, the retry-penalty ordinal) are per **instance**, not per
student. The loader therefore fans each announcement template out into a
**dedicated instance per assigned student** (6 Biology students × 4
announcements = 24 sheets, plus 4 for Pharmacy = 28 total). All students in an
announcement share the same correct ion set here; in a real course each sheet
would carry its own composition.

## Quick start

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py load_examples --reset   # load (or reload) the dataset
uv run python manage.py runserver               # http://127.0.0.1:8000
```

The frontend must be built once (see the repo `README.md`):
`npm --prefix frontend run build`. The dev server proxies `/api` to port 8000.

Reload any time with `load_examples --reset` (idempotent without `--reset`;
time windows are always re-based on "now").

## Demo logins

All accounts share the password **`FlameCheck-Demo-123`**.

| Username | Role | Notes |
|---|---|---|
| `admin` | admin | full admin API (`/api/v1/admin/…`), Django admin (`/admin-django/`) |
| `assistant.bio` | assistant | sees the Biology course only |
| `assistant.pharma` | assistant | sees the Pharmacy course only |
| `student-anna` | student | Biology; sheet #1 already submitted with a perfect score (20) |
| `student-ben` | student | Biology; sheet #1 submitted twice (10, then 18 after the retry penalty) |
| `student-david` … `student-felix` | student | Biology; fresh, unsubmitted |
| `student-greta`, `student-hugo` | student | Pharmacy; fresh, unsubmitted |

Barcode login (as the real scanner does): `POST /api/v1/auth/barcode/scan`
with e.g. `{"barcode": "FC-DEMO-0004"}` (student-david).

### What to try

- **student-david**: sees 4 sheets — #1 and #2 *open*, #3 *too early*
  (opens tomorrow), #4 *too late* (closed yesterday). Submit on sheet #2
  (possible ions: Cl⁻, Br⁻, SO₄²⁻, CO₃²⁻, NO₃⁻; correct: Cl⁻ + SO₄²⁻).
  You get up to 3 attempts; retries cost 2/4 points. After the first accepted
  submission the answer key is revealed at the *result* endpoint.
- **assistant.bio**: course roster with barcodes, live stats (submitted /
  pending / average score), per-student submission detail including the answer
  key, and a CSV export.
- **admin**: create courses / analysis types / instances / assignments,
  adjust the grading configuration and the active course.

## Verifying the full app

With the server running and a **fresh** dataset loaded
(`load_examples --reset`), in a second terminal:

```bash
uv run python examples/verify_demo.py
```

The script drives the real stack over HTTP and asserts 54 checks across:

1. **frontend** — built SPA index, hashed JS/CSS chunks and favicon all serve,
2. **auth** — password + barcode login, wrong-credential and unknown-barcode
   rejection, refresh-token rotation, logout token revocation,
3. **student flow** — analysis list with all four window states, detail with
   the possible-ion set (answer key hidden), reference substances, scoring
   (full marks, retry penalty, third-attempt penalty), idempotent replay,
   disallowed-ion rejection, submission-limit enforcement, result endpoint,
   per-student summary,
4. **seeded data** — anna's perfect 20 and ben's 10 → 18 retry pair,
5. **assistant** — roster, stats, per-student submissions, CSV export,
   course isolation between assistants,
6. **admin** — course/type/instance/assignment listings, course creation,
   grading-config round-trip, active-course settings,
7. **catalog & RBAC** — 22 ions / 35 substances, filtering, and
   student-vs-admin permission boundaries.

Exit code 0 means every check passed.
