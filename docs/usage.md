(usage)=

# Usage

Assuming you have followed the {ref}`installation steps <installation>`, the app is
ready to use. This page describes the main workflows from the perspective of each
role.

## Roles

| Role      | Description                                                       |
|-----------|-------------------------------------------------------------------|
| Student   | Submits ion analyses within the open time window.                 |
| Assistant | Views the roster, per-student submissions and statistics.         |
| Admin     | Manages courses, analysis types/instances, grading and settings.  |

## Students

1. **Log in** on the login page with your username and password (the password
   field has a show/hide toggle).
2. The home page lists every analysis assigned to the student with its current
   window state (`Open`, `Not Open Yet`, `Closed`, `Submitted`).
3. Open an analysis while its window is **open**: pick the cations and anions that
   were detected, then **Submit Analysis**. Submission is final; a confirmation
   dialog is shown first.
4. After submitting (or once the window has closed) the **result** is revealed,
   including the score, the per-ion breakdown and the correct answer key.
5. **Multiple-choice cards** (when the course has any) are listed below the
   analyses, each with its own time window. Open a card while the window is
   **open**, pick one option per question, and submit. A fully correct card
   earns the course's points-per-card; each wrong answer deducts the configured
   penalty.

Submissions are immutable and timestamped. A client-generated idempotency key
guarantees that a retried submission does not create a duplicate. Retries are
penalised according to the grading configuration (second attempt, third attempt).

## Assistants

1. Log in with an assistant account.
2. The assistant dashboard lists every course they are assigned to, with aggregate
   statistics (total assignments, submitted, pending, average score).
3. Expand a course to see the full roster with each student's barcode and progress.
   Click a student's row (or its **Details** link) to open the **per-student
   statistics** view: overall numbers (analyses, submitted, total / average /
   best score) plus a per-analysis breakdown showing the correct ion set, the
   final score, and the full submission history (each attempt's score,
   correct / wrong / missing counts, retry penalty and selected ions).
4. Use **Download CSV** to export the full submission audit log for a course.
5. Use **Substance Overview** to plan lab preparation: for every analysis of the
   course it lists the substances that share at least one of the analysis'
   correct ions, and aggregates the total number of substance units over the
   whole course. The number of samples per analysis is configurable (by
   default one sample per assigned student).

## Admins

1. Log in with an admin account.
2. The admin panel (`/admin`) has a navigation bar with one dedicated page
   per concern:
   - **Settings** — every setting of the submission system in one place:
     the *application settings* (points per analysis, analyses per course,
     the currently active course), the *global grading configuration*
     (mode, points, penalties, submission limit, final-score strategy,
     pass mark, multiple-choice points), the *registration mode*, the
     *e-mail notification* settings (SMTP + PGP) and the *database* backup
     controls.
   - **Courses** — create, edit and delete courses (name, semester, track,
     active, and the per-course *notify the student* e-mail switch). Open
     *Students* on any course to see who is enrolled there and remove
     students; assign a student to a course from here. Each course also has a
     *Grading* card with its own (overriding) grading configuration — see
     {ref}`Grading <grading>`.
   - **Analysis Types** — the user-defined analysis catalog. Create, edit and
     delete types and pick each type's possible ion set; click a row to open
     the edit form.
   - **Substances** — the substance catalog. Import and export the catalog as
     CSV; click a row to edit a substance (name, synonyms, formula, ion set
     and the PubChem / Wikipedia reference).
   - **Multiple Choice** — the per-course multiple-choice designer. Select a
     course, then define *questions* (text, options with one correct answer,
     plus a description and remarks for your own documentation), group up to
     three questions into a *card*, and present a time-windowed *sheet* to
     chosen students. The page also holds the course's multiple-choice
     grading (points per fully correct card, penalty per wrong answer).
   - **Assignments** — pick a course to see its analysis sheets (instances);
     open *Manage* on a sheet to choose which students receive it (and the
     announcement number).
   - **Ion symbols** — ions are written in one canonical form,
     `<formula><sign><magnitude>` with the digit always present (e.g. `Na+1`,
     `Mg+2`, `SO4-2`). When you create an ion or import substances by CSV the
     symbol is normalized to this form automatically (Unicode IUPAC charges
     such as `SO₄²⁻` and extra whitespace are accepted); the charge and
     cation/anion kind are derived from the symbol. The full rule set, the
     IUPAC display form and the migration from the old notation are described
     in {doc}`the ion symbol convention <development/ion_symbol_convention>`.
3. The same settings are also editable in the standard Django admin
   (`/admin-django/`, reachable via the "Django admin" link in the SPA admin
   panel). Each setting has its own edit page: open *Grading configuration* or
   *Application settings* and click the row to get a dedicated change form with
   the fields grouped into labelled sections (e.g. *Scoring mode* /
   *Penalties & limits*), or quick-edit a subset of values directly in the
   change list.
   Analysis instances (concrete sessions with a time window and the correct
   ion set) and student assignments are managed through the admin API and the
   Django admin.

## API

The REST API lives under `/api/v1/`. In DEBUG mode the interactive OpenAPI
documentation is available at `/api/v1/docs` and the machine-readable schema at
`/api/v1/openapi.json`.

Authentication is via JWT bearer tokens:

- `POST /api/v1/auth/login` — username/password login.
- `POST /api/v1/auth/barcode/scan` — barcode login.
- `POST /api/v1/auth/token/refresh` — rotate the access token.
- `POST /api/v1/auth/logout` — invalidate the current token version.
- `GET /api/v1/me` — current user profile.

The full setup — how accounts are created, all sign-in methods (password,
barcode, self-registration, OAuth/Keycloak), the token lifecycle and the
registration modes — is described on the
{ref}`Registration & authentication <registration>` page.

For the mechanics of the tasks themselves, see
{ref}`Analyses <analyses>`, {ref}`Multiple choice <multichoice>` and
{ref}`Grading <grading>`.
