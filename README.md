<p align="center">
  <img src="docs/_static/flamecheck_logo.svg" alt="FlameCheck — a Bunsen-burner flame with a checkmark" width="160" height="160"/>
</p>

<h1 align="center">FlameCheck</h1>

<p align="center">
  <a href="https://www.djangoproject.com/"><img alt="Django 6" src="https://img.shields.io/badge/Django-6.x-092E20"></a>
  <a href="https://www.python.org/"><img alt="Python 3.13" src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white"></a>
  <a href="https://vuejs.org/"><img alt="Vue 3" src="https://img.shields.io/badge/Vue-3.x-42B883?logo=vue.js&logoColor=white"></a>
  <a href="https://uv.pypa.io/"><img alt="uv" src="https://img.shields.io/badge/uv-workspace-20C49E?logo=python&logoColor=white"></a>
  <a href="https://www.sqlite.org/"><img alt="SQLite default" src="https://img.shields.io/badge/SQLite-default-003B57?logo=sqlite&logoColor=white"></a>
  <a href="https://www.postgresql.org/"><img alt="PostgreSQL optional" src="https://img.shields.io/badge/PostgreSQL-optional-336791?logo=postgresql&logoColor=white"></a>
  <a href="https://opensourcelab.gitlab.io/cheminformatics/flamecheck/"><img alt="Documentation" src="https://img.shields.io/badge/docs-GitLab%20Pages-FF6B35?logo=gitlab"></a>
</p>

<p align="center">
  A web system for first-semester inorganic chemistry students to submit<br/>
  qualitative ion-analysis results and multiple-choice cards — scanned, time-gated, and auto-graded.
</p>

---

## What is FlameCheck?

FlameCheck is a **web-based submission system for inorganic qualitative
analysis**.  Chemistry students authenticate with their
**university login** (e.g. Shibboleth / LDAP / Keycloak) or a **personal barcode**,
see the cations and anions that are possible for their assigned analysis, and
tick the ions they believe are present. The system **automatically scores** the
submissions, supports **user-defined analysis types** (e.g. for lab courses
specialising in biology, pharmacy, geology, medicine or materials science), and
allows **multiple analyses per student, each with its own submission time window**.
In addition to the ion analyses, a course can contain **multiple-choice cards**
(e.g. flame-test questions or pharmacopoeia monographs) that are graded the same
way — time-gated, immutable, and accumulated into the course total.

> ⏱️ Every analysis and every card is subject to a **date/time window** —
> submissions that are too early or too late are rejected, and the final result
> and point allocation are awarded at the end.

### Key capabilities

- **Flexible authentication** — username/password, **personal barcode** (webcam
  or USB keyboard-wedge scanner via ZXing), **self-registration** with e-mail
  confirmation, or **OAuth / OpenID Connect** (e.g. Keycloak) — one
  *registration mode* controls which path creates student accounts.
- **Time-window gating** per analysis and per card with live status: `open`,
  `too early`, `too late`, `submitted`.
- **Immutable, timestamped submissions** with a client-generated **idempotency
  key** (retries never create duplicates).
- **Two scoring modes** — *per-ion* (default) or *per-analysis*
  (all-or-nothing) — with configurable retry penalties, an optional
  false-positive deduction, and a **final-score strategy** (best or last
  submission).
- **Two submission workflows** — *resubmit* (the student retries the same sheet,
  up to a configurable limit) or *new analysis* (a wrong answer hands out a
  fresh, randomly composed analysis of the same type, up to the type's maximum
  repetitions — the assistant is notified).
- **Per-course grading configuration** — one global default plus an optional
  override per course (mode, points, penalties, limits, pass mark, multiple-choice
  points), so a single installation can run differently graded courses side by side.
- **Multiple-choice cards** — questions with options, grouped into cards (up to
  three questions), presented as time-windowed sheets; a fully correct card earns
  the course's points-per-card, each wrong answer deducts the configured penalty.
- **Assistant views** — per-course roster, per-student submissions and
  statistics, re-trial notifications, substance-overview planning and a
  **CSV audit export**.
- **Admin configuration** — ion & substance catalog, analysis types/instances,
  assignments, barcodes, time windows, points, grading modes, multiple-choice
  designer, and application settings.
- **PGP-encrypted and signed e-mail notifications** — optional submission
  confirmations to the student (per-course) and to the assistants (global),
  gated by the `ALLOW_EMAILS` environment variable so demo/staging instances
  never send e-mail.
- **Role-based access** (Student / Assistant / Admin) enforced on every
  endpoint, with brute-force lockout, JWT revocation and full audit logging.
- **Runs anywhere** — SQLite by default (zero external services), PostgreSQL
  optional; a single production Docker image plus compose files for
  production, staging and development.

📚 **Documentation:** the complete guide — installation (all Docker variants,
SQLite / PostgreSQL), usage, the analysis / multiple-choice / grading options
with worked examples, registration & authentication, an admin course-setup
walkthrough, and DevOps deployment notes — is published on
[GitLab Pages](https://opensourcelab.gitlab.io/cheminformatics/flamecheck/).

For the complete requirements see the
[software specification](docs/development/flamecheck_software_specification.md),
and for the deep-dive on how everything fits together — with architecture
diagrams — see the
[architecture documentation](docs/development/architecture.md).

---

## Tech stack

| Layer        | Technology |
|--------------|------------|
| Backend      | Django 6 + **django-ninja** REST API |
| Auth         | **PyJWT** (HS256, `token_version` revocation) + django-allauth (SSO / OAuth) |
| Frontend     | **Vite 8 · Vue 3 · Pinia · Vue Router · Naive UI** |
| Barcode scan | **@zxing/browser** (webcam + manual/USB fallback) |
| Database     | **SQLite by default**; PostgreSQL optional (set `DATABASE_URL`) |
| E-mail       | **GnuPG** (PGP sign + encrypt) + `smtplib` |
| Tooling      | **uv** workspace, ruff, mypy, pytest, WhiteNoise, Gunicorn |

---

## Project layout

```
flamecheck/
├── .env-template          # env template (copy to .env); DB, JWT, superuser, demo
├── docker-compose.yaml            # production compose (SQLite default, Postgres opt-in)
├── docker-compose-staging.yaml    # staging compose (boots with the demo dataset)
├── docker-compose-dev.yaml        # development compose (autoreloading dev server)
├── src/flamecheck/        # Django project: settings, URLs, ninja API wiring
│   └── settings/          #   base / development / production / test
├── packages/              # uv workspace members
│   ├── users/             #   User, barcodes, JWT auth, login API, assignments
│   ├── substances/        #   Ion + Substance catalog (+ JSON seed data)
│   ├── config/            #   Course, GradingConfig, AppSettings, e-mail service
│   ├── analyses/          #   AnalysisType/Instance/Submission + scoring + retry
│   └── multichoice/       #   Questions, options, cards, sheets + MC scoring
├── frontend/              # Vite 8 + Vue 3 SPA
├── tests/                 # pytest suite
├── docker/                # Dockerfiles + entrypoints (+ a dev-full compose)
└── docs/                  # Sphinx docs (development/ has spec + architecture)
```

A full annotated tree, the entity-relationship diagram and the request
lifecycle are in the [architecture documentation](docs/development/architecture.md).

---

## Installation

> **Prerequisites:** Python **3.13**, [`uv`](https://docs.astral.sh/uv/), and
> Node.js **20+** (frontend). **No database is required to start** — SQLite is
> the default and needs no external service. PostgreSQL is optional.

### Development

The default backend is **SQLite** (a `db.sqlite3` file at the repo root), so the
steps below need nothing beyond `uv` and Node.

```bash
# 1. Get the code
git clone <repository-url> flamecheck
cd flamecheck

# 2. (Optional) copy the environment template. Everything works without it,
#    because the defaults are SQLite + development.
cp .env-template .env

# 3. Python environment (creates .venv, installs the workspace packages)
uv sync

# 4. Frontend dependencies + build (output → frontend/dist/)
npm --prefix frontend install
npm --prefix frontend run build

# 5. Database schema (SQLite by default) + seed the ion/substance catalog
uv run python manage.py migrate
uv run python manage.py import_catalog

# 6. (Optional) load a rich demo dataset — 5 courses (Geology, Chemistry,
#    Biology, Medicine, Materials), 21 users, 12 analysis types, per-student
#    sheets, MC cards and graded submissions (all accounts share the password
#    FlameCheck32!). Use --reset to wipe and re-seed the domain from scratch.
uv run python manage.py seed_demo

# 7. Create a first admin user (credentials come from .env — see
#    DJANGO_SUPERUSER_* in .env-template), then set its role to `admin`.
uv run python manage.py init_admin
uv run python manage.py shell -c "from users.models import User; User.objects.filter(username='admin').update(role='admin')"

# 8. Run the dev server
uv run python manage.py runserver
```

Open:

- <http://127.0.0.1:8000/> — the app
- <http://127.0.0.1:8000/api/v1/docs> — interactive OpenAPI documentation (DEBUG only)
- <http://127.0.0.1:8000/admin-django/> — Django admin (also linked from the SPA admin panel)

**Frontend hot-reload:** run `npm --prefix frontend run dev` in a second
terminal. The Vite dev server on `:5173` proxies `/api` to the Django server on
`:8000`, so you can develop the SPA with live HMR while hitting the real API.

**Optional — create a test student barcode** to try barcode login:

```bash
uv run python manage.py init_barcode
```

### Production

Production runs the Django project under **Gunicorn** (WSGI) with **WhiteNoise**
serving the built frontend. **The database is configurable through `.env`**:
the default is **SQLite** (no external service), or **PostgreSQL** when you set
`DATABASE_URL` to a `postgres://` URL. The recommended deployment is **Docker
Compose** behind a reverse proxy that terminates TLS.

```bash
# 1. Configure the environment (copy the template and edit)
cp .env-template .env
#    -> set ENV=production, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, and
#       DATABASE_URL if you want PostgreSQL (see .env-template for examples).

# 2. Build and start. SQLite (default) is a single container:
docker compose -f docker-compose.yaml --env-file .env up --build -d

# 3. To use PostgreSQL instead, activate the profile (it starts a Postgres
#    container) and set DATABASE_URL in .env first. Install the driver:
uv sync --extra postgres
docker compose -f docker-compose.yaml --env-file .env --profile postgres up --build -d
```

The entrypoint (`docker/entrypoint.production.sh`) runs `migrate` +
`collectstatic` and then starts Gunicorn. It is engine-agnostic — it does the
same thing for SQLite and PostgreSQL. Key production settings live in
`src/flamecheck/settings/production.py` (select it with
`DJANGO_SETTINGS_MODULE=flamecheck.settings.production`): secure cookies, HTTPS,
HSTS, WhiteNoise-compressed static serving and the Gunicorn worker count
(`GUNICORN_WORKERS`).

For all compose variants (production / staging / development / dev-full stack),
the SQLite vs. PostgreSQL decision, and how to place the stack behind a
load-balancer or TLS-terminating web server, see the
[deployment documentation](docs/deployment.md).

### Staging

A pre-production environment that mirrors production (same image, same
Gunicorn entrypoint) but runs with **debugging enabled** and a separate default
port (8001). It **boots with the demo dataset already loaded** — five courses,
21 users, analyses, MC cards and a handful of graded submissions (every demo
account shares the password `FlameCheck32!`) — so it is ready to explore out of
the box.

```bash
cp .env-template .env
#    -> set DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, and (optionally) APP_PORT.

# Build and start (SQLite default; the demo dataset is seeded on boot):
docker compose -f docker-compose-staging.yaml --env-file .env up --build -d

# Re-seed the demo dataset from scratch (wipe the seeded domain first):
SEED_DEMO=reset docker compose -f docker-compose-staging.yaml --env-file .env up --build -d
```

Seeding is controlled by the `SEED_DEMO` variable (default `true` in the
staging compose, unset elsewhere): `true` re-seeds idempotently, `reset` wipes
and re-seeds, and an empty value skips it.

> **TLS / reverse proxy.** In front of the container, use Nginx (or Caddy with
> automatic Let's Encrypt) to serve over HTTPS and proxy `/api/` and `/static/`
> to the Django process. The SPA is same-origin, so no CORS configuration is
> required in production.

---

## Usage

### Students

1. **Log in** on the login page — scan your personal barcode (webcam or manual
   entry) or sign in with username/password (or via the configured OAuth
   provider).
2. The home page lists every **assigned analysis** with its live window status
   (`Open`, `Not Open Yet`, `Closed`, `Submitted`), plus any **multiple-choice
   cards** of the course.
3. Open an analysis while its window is **open**: tick the cations and anions
   you detected. The **possible** ion set is shown — never the correct one.
4. **Submit** — a confirmation dialog summarises your selection because
   submissions are **final** and immutable.
5. The **control query** immediately reveals the result: correct / wrong /
   missing ions, the score, and the ideal score.
6. Open a **multiple-choice card** while its window is open, answer every
   question, and submit — a fully correct card earns the course's
   points-per-card, each wrong answer deducts the configured penalty.
7. A student may complete several analyses and cards (e.g. the 3rd and 4th
   announcement); each is scored independently and accumulated into the
   **final course result** (with a configurable pass mark).

Retries are handled according to the course's grading configuration: in
*resubmit* mode the student retries the same sheet up to a limit (per-ion mode
penalises the 2nd/3rd attempt by default **−2 / −4**), or in *new analysis* mode
a wrong answer hands out a fresh re-trial analysis. A client idempotency key
guarantees a retried request never creates a duplicate submission.

### Assistants

- See every assigned **course** with aggregate statistics (total assignments,
  submitted, pending, average score).
- Drill into the **roster** — each student's barcode, labspace id, assigned
  analyses and submission status.
- View **individual student submissions** including the selected and the
  **correct** ions.
- Receive **re-trial notifications** when a "new analysis" workflow hands out a
  fresh sheet.
- Use **Substance Overview** to plan lab preparation (substances per analysis
  and course-wide totals).
- **Download a CSV** audit log for a course.

### Admins

- **Courses** — create/list courses (name, semester, track, active, e-mail
  confirmation switch); enrol members (students and assistants), manage
  barcodes.
- **Grading** — a global default configuration **and** per-course overrides:
  grading mode (per-ion / per-analysis), submission workflow (resubmit / new
  analysis), points, retry penalties, false-positive deduction, submission
  limit, final-score strategy (best / last), pass mark, and multiple-choice
  points/penalty.
- **Analysis types & instances** — define the possible-ion sets and concrete
  sessions (time window + correct answer set + label), then assign them to the
  students of a **course** (the Courses view is the admin landing page).
- **Multiple Choice** — the per-course designer: questions, options, cards,
  time-windowed sheets, assignment to students, and the MC grading.
- **Ion / substance catalog** — importable from JSON/CSV.
- **Settings** — application settings, registration mode, e-mail notifications
  (SMTP + PGP), branding, and database backup/restore.

### REST API

The REST API lives under `/api/v1/`. In DEBUG mode the interactive OpenAPI docs
are at `/api/v1/docs` and the machine-readable schema at `/api/v1/openapi.json`.
Authentication is via JWT bearer tokens:

| Method & path | Purpose |
|---|---|
| `POST /api/v1/auth/login` | Username/password login |
| `POST /api/v1/auth/barcode/scan` | Barcode login (generic 401 for unknown/inactive) |
| `POST /api/v1/auth/token/refresh` | Rotate the access token |
| `POST /api/v1/auth/logout` | Revoke the current token version |
| `GET /api/v1/me` | Current user profile |

Student, assistant and admin endpoints are documented in the
[architecture documentation](docs/development/architecture.md#7-api-surface).

---

## Testing

```bash
uv run pytest            # full backend suite (456 tests, coverage → coverage.xml)
```

The suite covers the REST API (auth, student, assistant, admin), the factories,
the scoring/grading logic, the e-mail notification service and the demo seeding.
End-to-end flows (login → submission → result) are exercised manually against a
running dev/staging instance. See
[§4.4 Testing](docs/development/flamecheck_software_specification.md) in the
specification.

---

## Development workflow

```bash
uv run ruff check --fix .   # lint (rules: B D C4 S F E W UP I RUF, line-length 120)
uv run ruff format .        # format
uv run mypy                 # type-check (disallow_untyped_defs)
uv run pytest               # tests
```

Commits follow **Conventional Commits** (`feat`, `fix`, `docs`, `chore`, …).

---

## Documentation

📚 The full documentation is published on
[GitLab Pages](https://opensourcelab.gitlab.io/cheminformatics/flamecheck/):

| Chapter | Contents |
|---|---|
| [Installation](docs/installation.md) | local development, all Docker variants, SQLite / PostgreSQL |
| [Usage](docs/usage.md) | student, assistant and admin workflows |
| [Analyses](docs/analyses.md) | types, instances, time windows, submission workflows — with examples |
| [Multiple Choice](docs/multichoice.md) | questions, cards, sheets, MC scoring — with examples |
| [Grading](docs/grading.md) | per-ion / per-analysis, penalties, pass marks — with worked examples |
| [Registration & Authentication](docs/registration.md) | account creation, OAuth/Keycloak, JWT lifecycle |
| [Course Setup](docs/course-setup.md) | the admin's end-to-end setup, with a flow diagram |
| [Deployment](docs/deployment.md) | Docker in production, reverse proxy / TLS / load-balancer |

Also:

- 📐 [Software specification](docs/development/flamecheck_software_specification.md) — requirements & rationale
- 🏛️ [Architecture](docs/development/architecture.md) — system design, ERD, API surface, diagrams
- 🔤 [Ion symbol convention](docs/development/ion_symbol_convention.md) — canonical ion notation

---

## License

FlameCheck is part of the OpenSourceLab cheminformatics collection. See the
repository's license file for terms of use and distribution.
