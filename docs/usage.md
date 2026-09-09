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

1. **Log in** on the login page using either a username/password or by scanning the
   student barcode (camera or manual entry).
2. The home page lists every analysis assigned to the student with its current
   window state (`Open`, `Not Open Yet`, `Closed`, `Submitted`).
3. Open an analysis while its window is **open**: pick the cations and anions that
   were detected, then **Submit Analysis**. Submission is final; a confirmation
   dialog is shown first.
4. After submitting (or once the window has closed) the **result** is revealed,
   including the score, the per-ion breakdown and the correct answer key.

Submissions are immutable and timestamped. A client-generated idempotency key
guarantees that a retried submission does not create a duplicate. Retries are
penalised according to the grading configuration (second attempt, third attempt).

## Assistants

1. Log in with an assistant account.
2. The assistant dashboard lists every course they are assigned to, with aggregate
   statistics (total assignments, submitted, pending, average score).
3. Expand a course to see the full roster with each student's barcode and progress.
4. Use **Download CSV** to export the full submission audit log for a course.

## Admins

1. Log in with an admin account.
2. The admin panel offers tabs for:
   - **Courses** — create and list courses (name, semester, track, active).
   - **Grading** — configure points per ion, retry penalties, false-positive
     deduction, grading mode (per ion / per analysis), submission limit and the
     final-score strategy (best / last).
   - **Analysis Types** — the user-defined analysis catalog with the possible ion
     sets per course track.
3. Analysis instances (concrete sessions with a time window and the correct ion
     set) and student assignments are managed through the admin API and Django
   admin.

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
