# Software Specification: Inorganic Analysis Submission System

## 1. Overview

**Purpose:** A web-based system for first-semester chemistry students to submit inorganic qualitative analysis results. Students authenticate with a university login (e.g., Shibboleth, ldap) or personal barcode, 
view the cations/anions possible for their assigned analysis, and tick the ions they believe are present. The system automatically scores submissions (e.g, 10 points per correctly identified analysis).
Additionally, some user defined analysis types should be possible, e.g. for specific lab courses with specialisation for biology, pharmacy, or materials science. The system supports multiple analyses per student, each with its own time window for submission.

**Inspiration from the attached document:** The provided "Ansagemodus" document describes an analogue process: a student scans a barcode from their analysis sheet at an announcement computer at the assistant's desk, the system shows which ions can occur, the student checks off ("Ankreuzen") the ions found and finishes the announcement, then a control query ("Kontrollabfrage") reveals the result. Several announcements (e.g., 3rd and 4th analysis) are possible, each subject to a **date/time window** ("Datum des Ansagezeitraumes beachten" – too early/too late submissions are rejected), ending in a final result and point allocation [1]. The web system replaces the desk computer and barcode scanner with browser-based barcode scanning while preserving this workflow.


## 2. User Roles

| Role | Capabilities |
|---|---|
| **Student** | Login via personal barcode, view assigned analyses within the valid time window, submit ion selections, view results and points |
| **Assistant** | Manage analysis sheets/barcodes, view submitted results per group, support students during announcement time |
| **Admin** | Manage users/barcodes, define analyses with their ion sets, set points per correct analysis (default 10), configure the number of analyses per course, set announcement time windows, view statistics |

## 3. Functional Requirements

### 3.1 Student Workflow
1. **Login:** Student scans their personal barcode (via webcam of smartphone/USB scanner through a browser barcode-scanning library, e.g. `html5-qrcode` or `@zxing/browser`) [1]. The barcode resolves to the student's identity and their assigned analysis sheet.
              - alternatively, a student logs in via a username/password or institutional SSO (e.g., Shibboleth) if barcode scanning is unavailable.
2. **Time-window check:** The system validates the current date/time against the announcement window for the analysis. Submissions are rejected if too early or too late (as in "zu früh!"/"zu spät!" [1]).
3. **Analysis display:** Depending on the assigned analysis, the form shows **all possible cations and anions** for that analysis (not the correct ones) [1].
4. **Submission:** Student ticks the ions they believe are present and confirms ("Submit") [1]. A second confirmation dialog, containing a summary of the selected ions, ensures they are ready to submit, as submissions are final and cannot be edited.
                   - important: submissions are timestamped and immutable; the system logs all actions for audit purposes.
5. **Control query & result:** Immediately after submission, the system reveals which ions were correct and awards **10 points per correctly identified analysis** [1].
                            - optionally, the system can deduct points for false positives if configured by the admin.
6. **Multiple announcements:** A student may perform several analyses (e.g., 3rd, 4th analysis) within the allowed window; each is scored independently and accumulated into the final result and point allocation [1].
7. **Final result:** After all assigned analyses, the student sees the total points and the ideal result ("Das Idealergebnis") [1].
8 . **Summary view:** The student can view a summary of all analyses, their scores, and the total points earned.

### 3.2 Assistant Workflow
1. **Login:** Assistant logs in via institutional SSO or username/password.
2. **View submissions:** Assistant can view all student submissions for their assigned group, including timestamps and scores.
3. **Support students:** Assistants can help students with barcode scanning issues, time-window questions, and general guidance during the announcement period.
4. **Statistics:** Assistants can view statistics on submissions, such as the number of students who have submitted, average scores, and common mistakes
5. **Per Student view:** Assistants can view individual student submissions, including the selected ions and the correct answers for each analysis.
6. **Course view:** Assistants can see the list of all students in their course, their assigned analyses, and their submission status (submitted/not submitted, points earned).
7. **Course management:** Assistants can manage the assignment of analyses to students, ensuring that each student has the correct analysis sheet and barcode for their assigned analysis.

### 3.3 Admin Configuration
- **Ion catalog:** Master list of all cations (e.g. Group I–IV/V: Na⁺, K⁺, NH₄⁺, Mg²⁺, Ca²⁺, Ba²⁺, Cu²⁺, Fe²⁺/Fe³⁺, Al³⁺, Zn²⁺, Mn²⁺, etc.) and anions (Cl⁻, Br⁻, I⁻, SO₄²⁻, SO₃²⁻, CO₃²⁻, PO₄³⁻, NO₃⁻, NO₂⁻, S²⁻, etc.).
                  - importable from CSV or JSON for easy updates.
                  - every ion is stored under a single **canonical symbol** of the
                    form `<formula><sign><magnitude>` (e.g. `Na+1`, `Mg+2`, `SO4-2`);
                    the magnitude digit is always present. Human input is
                    normalized to this form (Unicode IUPAC charges such as `SO₄²⁻`
                    and whitespace are accepted) and the `charge` / `kind` are
                    derived from the symbol. See
                    {doc}`ion_symbol_convention` for the full specification.
- **Substance catalog:** Optional mapping of ions to common salts (e.g., NaCl, KBr, CuSO₄) for reference.
                      - substance catalog should be importable from CSV or JSON for easy updates.
                      - ions should be deducible from substances, but the system should allow for ions to be defined independently of substances.
- **Analysis definition:** Each analysis type defines (a) the **set of possible ions** shown to students, and (b) the **correct answer set** per concrete analysis instance (e.g., "Analysis 12: contains NH₄⁺, SO₄²⁻, Cu²⁺").
- **Points per correct analysis:** Admin-adjustable, default **10** [1].
- **Number of analyses per course/semester:** Admin-adjustable (e.g., 2, 3, 4 announcements per student) [1].
- **Time windows:** Per-analysis start/end date and time for each submission controlled by the admin (e.g., "3rd analysis: 2026-11-01-2026-11-30 10:00–12:00h") [1].
                    - UI should display the current status: "open", "too early", "too late", or "submitted".
- **Barcodes:** Generate and assign unique barcodes (Code128 or QR) to students/analysis sheets.
- **Multiple choice (per course):** In addition to the analyses, a course can
  carry multiple-choice cards. An admin defines, per course:
  - **Questions:** a text, a list of options with exactly one marked correct,
    plus a *description* and *remarks* field (admin-only documentation,
    editable in the designer UI).
  - **Cards:** a grouping of **1 to 3 questions** (the unit a student answers).
  - **Sheets:** a time-windowed presentation of a card, assigned to chosen
    students (mirroring the analysis instance window/assignment model).
  A dedicated admin *Multiple Choice* page is the designer for all three.

### 3.3 Grading Logic
- **Per-ion mode (default, as described):** 
    - 10 (default) points per correctly identified ion - admin configurable.;
    - 10 - 2 points (default) per corrected 2nd submission (if allowed) - penalty admin configurable.
    - 10 - 4 points (default) per corrected 3rd submission (if allowed) - penalty admin configurable.
    - number of submissions per analysis can be limited (e.g., 1–3) by admin.
    - optionally configurable to deduct points for false positives.
- **Per-analysis mode (alternative, admin-selectable):** 10 points only if the full ion set is exactly correct.
- **Multiple choice (per course):** a fully correct card earns the course's
  *points per card* (default **10**); each wrongly answered question deducts
  the course's *penalty per wrong answer* (default **2**). The card score is
  the points minus the penalty times the number of wrong answers, floored at
  zero. Both values are per-course configurable (alongside the analysis
  grading).
- Results are final upon submission (no editing), consistent with the "Kontrollabfrage → Ergebnis" flow [1].

## 4. Technical Architecture

### 4.1 Backend — Django
- **Django 6.x + django Ninja** REST API.
     - use models.Manager, where appropriate, to encapsulate business logic (e.g., submission validation, scoring).
- **SQLite** (default) or **PostgreSQL** database. The backend is selected through the `DATABASE_URL` variable in the `.env` file (see `.env-template`); the default is a local SQLite file, and PostgreSQL is opt-in.
- **Authentication:** Token-based (JWT) for API; session cookie for web frontend. Django allauth (with shibboleth support) for login (students, assistants, admins).
- **Models (core):
  - separate apps for `users`, `analyses`, `substances`, `config`, `multichoice`:
  - `User` (extends Django user; role: student/assistant/admin), `StudentBarcode` (unique barcode value, FK student)
  - `Ion` (name, symbol, charge, type: cation/anion, group)
  - `Substance` (name, synonyms, formula, ions M2M, pubchem ids, wikipedia link)
  - `AnalysisType` (name, list of possible ions)
  - `AnalysisInstance` (FK AnalysisType, FK assigned student, correct ion set, time window start/end, status, score)
  - `Submission` (FK AnalysisInstance, selected ions M2M, timestamp, score, auto-graded)
  - `Config` (points per correct analysis, analyses per course, active course; also the per-course multiple-choice grading: points per card, penalty per wrong answer)
  - `MCQuestion` (FK course, text, description, remarks, options), `MCOption` (FK question, text, is_correct, order)
  - `MCCard` (FK course, title, description, remarks; 1–3 ordered questions), `MCSheet` (FK card, FK course, time window, number, student assignments), `MCSubmission` (FK sheet, FK student, answers, timestamp, score, auto-graded)
- **API endpoints:**
  - `POST /api/v1/auth/barcode/scan/` → validates a barcode server-side, applies rate limits, and returns a short-lived access/refresh token pair plus the authenticated user's role and assigned analyses. It must not disclose whether an unrecognized barcode belongs to another user.
  - `POST /api/v1/auth/login/` → username/password login for users without barcode access; institutional SSO uses the configured OIDC/Shibboleth callback and issues the same token format.
  - `POST /api/v1/auth/token/refresh/` and `POST /api/v1/auth/logout/` → rotate/revoke tokens.
  - `GET /api/v1/me/` → current user, role, course/lab, and minimal profile data.
  - `GET /api/v1/analyses/` → assigned analysis instances with type, number, window status (`open`, `too_early`, `too_late`, `submitted`), submission count/limit, and score; students may access only their own instances.
  - `GET /api/v1/analyses/{analysis_id}/` → analysis details and the complete possible-ion set, without exposing the correct-ion set before submission.
  - `GET /api/v1/analyses/{analysis_id}/substances/` and `GET /api/v1/analyses/{analysis_id}/substances/{substance_id}/` → related reference substances and details, subject to the analysis configuration.
  - `POST /api/v1/analyses/{analysis_id}/submissions/` → accepts a selected-ion ID list and an explicit confirmation flag; atomically checks ownership, window, submission limit, and allowed ions, creates an immutable timestamped submission, grades it according to the configured per-ion or per-analysis mode, and returns the result. Replays and duplicate requests must not create another submission (idempotency key required).
  - `GET /api/v1/analyses/{analysis_id}/submissions/` → the student's own submission history and scores, if multiple attempts are enabled.
  - `GET /api/v1/analyses/{analysis_id}/result/` → result for the student's completed submission(s), including correct, incorrect, and missing ions, score, penalties, and ideal score; unavailable until submission is accepted.
  - `GET /api/v1/me/summary/` → all assigned analyses, per-analysis scores/statuses, total and ideal points, and final result.
  - Assistant endpoints under `/api/v1/assistant/` → assigned-course roster, analysis assignments, submission details, status/statistics, and CSV export; read access to correct answers is restricted to assistants for their courses.
  - Admin CRUD under `/api/v1/admin/` → users, courses, assignments, barcodes, ions, substances, analysis types/instances, correct-ion sets, time windows, grading configuration, and audit-log/result exports. Mutating operations require admin authorization and are audited.

  All protected endpoints require authentication and enforce role, course, and object-level permissions. Mutating requests use CSRF protection where applicable, validate IDs server-side, and return consistent JSON errors (`code`, `message`, `field_errors`). The API must use UTC timestamps, pagination on collection endpoints, optimistic concurrency where configuration can change, and never expose correct answers or another student's data through list/detail responses.
- **Barcode verification** is server-side (barcode → DB lookup), never trust client.
- **Security:** - HTTPS, hashed credentials, rate-limiting on submission endpoint, one-time barcode per analysis window. 
                - save docker environment - safety hardend (e.g., no root, non-default ports, firewall rules).
                - Intrusion possibilities minimized by using Django's built-in security features (CSRF, XSS protection, etc.).
                - extra hardening: Docker container isolation, minimal base images, regular security updates.
                - prevent brute-force attacks: rate limiting, account lockout after multiple failed attempts, CAPTCHA for repeated failed logins.
                - prevent student hacking: barcodes are unique per student and analysis, submissions are timestamped and immutable, and the system logs all actions for audit purposes.

### 4.2 Frontend — Vue 3 + Vite
- **Vue 3** (Composition API, `<script setup>`), **Vite**, **Pinia** for state, **Vue Router**. Use latest vite technologies for fast development and hot module replacement.
- **UI library:** Naive UI or PrimeVue (modern, form/checkbox components).
- **UI design:** Responsive layout for desktop/laptop, tablet and mobile (students may use lab computers or laptops or their smartphones).
                 - modern, appealing design with clear feedback on submission status, time windows, and results.
                 
- **Barcode scanning:** `@zxing/library` or `html5-qrcode` — supports both webcam scanning and USB keyboard-wedge barcode scanners (which act as fast keystroke input ending in Enter).
- **Key views:**
  1. `LoginView` – barcode scan (webcam viewfinder + fallback USB/keyboard input)
  2. `AnalysisListView` – assigned analyses with time-window status (open / too early / too late / submitted)
  3. `SubmissionFormView` – two-column checkbox form (cations | anions), confirm button, submission deadline countdown
  4. `ResultView` – control-query style feedback: ticked ions highlighted green (correct) / red (wrong), missing correct ions shown, points earned
  5. `SummaryView` – all analyses, total points, ideal result comparison
  6. `AdminDashboard` (separate route) – ion/analysis/student management, time windows, points config, submission statistics
- **Responsive** design for laptop/tablet use at lab desks.


### 4.4 Testing
- **Backend:** Pytest for unit tests (models, API endpoints), coverage reports.
- **Frontend:** Vitest + Vue Test Utils for component/unit tests, Cypress for end-to-end testing (login, submission, result display).
- **Integration tests:** Docker Compose environment with test database, simulating student submissions and admin actions.

#### Test data with factory-boy + Faker

All test fixtures are built with **factory-boy** factories that live *inside* each
Django app (one `factory.py` per app: `users`, `substances`, `config`, `analyses`),
so the factories sit next to the models they build and can be imported anywhere the
domain is tested. They use **Faker** (bundled with factory-boy) for realistic random
values and the full factory-boy toolbox:

| Feature | Where it is used |
|---|---|
| `Faker` | Realistic names, emails, companies, IPs, datetimes, formulas, URLs, matriculation numbers |
| `Sequence` | Guaranteed-unique values (`username`, `labspace_id`, ion `symbol`, `pubchem_id`) |
| `SubFactory` | Building object graphs inline (barcode → student, instance → type/course, assignment → student/instance) |
| `LazyFunction` / `LazyAttribute` | Values computed at build time (fresh UUID idempotency keys, window datetimes, per-instance lists) |
| `post_generation` | Optional M2M / FK relations (possible/correct/selected ions, substance ions, course enrollment) |
| `django_get_or_create` | Idempotent creation keyed on natural keys (`username`, `(symbol, kind)`, `name`, `pk=1`) |
| `create_batch` / `make` | Bulk creation and named catalog helpers (`IonFactory.make('copper')`, `create_ion_catalog([...])`) |
| Custom `_create` | `UserFactory` routes through `create_user`/`create_superuser` so passwords are **hashed**; `AdminUserFactory`/`AssistantUserFactory` are ready-made role sub-factories |
| Singleton factories | `GradingConfigFactory`/`AppSettingsFactory` pin `pk=1` so repeated calls return the same row |

Concretely:

- **`users/factory.py`** — `UserFactory` (role field + `AdminUserFactory`/`AssistantUserFactory`), `StudentBarcodeFactory`, `LoginAttemptFactory`, `StudentAssignmentFactory`.
- **`substances/factory.py`** — `IonFactory` with a named first-semester catalog (`ION_CATALOG` + `IonFactory.make(name)` + `create_ion_catalog(names)`), and `SubstanceFactory` (ions via `post_generation`).
- **`config/factory.py`** — `CourseFactory`, `GradingConfigFactory` (singleton), `AssistantCourseFactory`, `AppSettingsFactory` (singleton).
- **`analyses/factory.py`** — `AnalysisTypeFactory`, `AnalysisInstanceFactory` (with an `AnalysisInstanceFactory.make(window='open'|'too_early'|'too_late')` helper that produces a window in the requested state relative to "now"), and `SubmissionFactory` (auto UUID idempotency key).

The shared fixtures in `tests/conftest.py` are thin wrappers over these factories (fixture
names are stable so test modules stay unchanged), and `tests/test_factories.py` exercises
the factories themselves (uniqueness, hashed passwords, M2M handling, idempotency,
window states, full-graph `SubFactory` building) — doubling as living documentation.

> **Note:** the project pins factory-boy 3.x, whose `Trait`/`Params` expansion does not
> interact reliably with a custom `_create` and `django_get_or_create` in the current
> environment. Named variants are therefore implemented with explicit field overrides,
> sub-factories and small `make()` helpers rather than `Trait`, which is the more robust
> pattern for this version.

### 4.3 Deployment
- Nginx serving built Vue assets + proxying API to Django (Gunicorn).
- Database configurable via `.env` (`DATABASE_URL`): **SQLite by default**, or **PostgreSQL** for larger deployments (the `db` service in the Compose file is opt-in via a profile).
- Docker Compose setup (web, plus optional db) for easy lab-room deployment.
- Deployment for development: local Docker Compose; staging: cloud VM with Docker Compose; production: cloud VM with Docker Compose + HTTPS (Let's Encrypt).

## 5. Non-Functional Requirements
- **Availability during announcement windows:** System must be up and fast (< 2 s response) during peak submission time.
- **Concurrent users:** Support 30–60 students submitting within a short window.
- **Audit:** All submissions timestamped and immutable; admin can export results as CSV.
- **Security:** HTTPS, hashed credentials, barcode as one-time-scannable token per window, rate-limiting on submission endpoint.
- **Privacy:** Student data minimal (name, matriculation number, lab, labspace-id, barcode, scores).

## 6. Data Model Sketch

```
Student (id, name, matriculation_no, barcode, role)
Ion (id, symbol, name, charge, kind: cation|anion, group)
Substance (id, name, formula, ions M2M[Ion], pubchem_id, wikipedia_link)
AnalysisType (id, name, possible_ions M2M[Ion])
AnalysisInstance (id, type FK, student FK, correct_ions M2M[Ion],
                  window_start, window_end, status, created_at)
Submission (id, analysis FK, selected_ions M2M[Ion],
            correct_count, wrong_count, score, submitted_at)
Config (points_per_analysis=10, analyses_per_course=3, course_active)
```

## 7. Scoring Example

Analysis 3's correct set: {NH₄⁺, SO₄²⁻, Cu²⁺}. Student ticks {NH₄⁺, SO₄²⁻, Cu²⁺} → all 3 correct == **10 points**. If student ticks {NH₄⁺, SO₄²⁻, Cu²⁺, Cl⁻} → 3 correct, 1 false positive → new submission possible if allowed, but may incur a penalty (e.g., -2 points) depending on admin configuration. If student ticks {NH₄⁺, SO₄²⁻} → 2 correct, 1 missing → 3rd submission possible if allowed, but may incur a penalty (e.g., -4 points) depending on admin configuration. After max. submissions, the final score is calculated based on the best submission or the last submission, depending on admin configuration.


