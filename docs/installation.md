(installation)=

# Installation

FlameCheck is a Django web application. It uses [`uv`](https://docs.astral.sh/uv/) for
Python dependency management and Node.js/Vite for the frontend.

## Prerequisites

- Python 3.13
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20+ (only for developing/building the frontend)

**No database is required to start.** The default backend is **SQLite** (a
`db.sqlite3` file at the repository root). **PostgreSQL is optional** and is
selected by setting `DATABASE_URL` in `.env` (see step 3 and the
[production notes](#production)).

## 1. Get the code

```bash
git clone <repository-url> flamecheck
cd flamecheck
```

## 2. Install the Python environment

```bash
uv sync
```

This creates a virtual environment in `.venv/` and installs all dependencies
from `pyproject.toml` (the Django project plus the `users`, `substances`,
`analyses` and `config` workspace packages).

## 3. Configure the environment (optional for local development)

Everything works out of the box with the defaults (SQLite, development mode),
so this step can be skipped for a quick local run. To customise, copy the
template and edit it:

```bash
cp .env-template .env
```

The template documents every variable. The most relevant for the database:

```dotenv
# SQLite (default — uncomment or leave unset):
#DATABASE_URL=sqlite:///db.sqlite3

# PostgreSQL (opt-in; install the driver first with `uv sync --extra postgres`):
#DATABASE_URL=postgres://flamecheck:flamecheck@localhost:5432/flamecheck
```

`django-environ` parses `DATABASE_URL` and maps it to Django's `DATABASES`, so
switching engines requires no code or migration changes.

### E-mail notifications (submission confirmations)

FlameCheck can send students and assistants a **PGP-encrypted and signed**
e-mail for every submission. The switches and the SMTP / PGP details are
configured in the UI (Admin → Courses for the per-course *student* switch, and
Admin → Settings → Notifications for the *assistant* switch plus SMTP / PGP).

As a safety layer, **no e-mail is ever sent unless the `ALLOW_EMAILS`
environment variable is enabled in the container** (defaults to `false`). This
prevents accidental e-mail delivery in staging and demo environments. To enable
it, set e.g. `ALLOW_EMAILS=true` in `.env` (or the container environment). The
Docker image ships with the `gnupg` package (the `gpg` binary) so the PGP
signing/encryption works out of the box.

## 4. Build the frontend

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

This emits the built Vue app into `frontend/dist/`, which Django serves for
all non-API routes. For live-reloading development use `npm --prefix frontend run dev`
(which proxies `/api` to the Django dev server on port 8000).

## 5. Create the database schema and seed data

```bash
uv run python manage.py migrate
uv run python manage.py import_catalog      # loads the ion + substance catalog
uv run python manage.py init_barcode        # (optional) create a test student barcode
```

Create an initial admin user:

```bash
uv run python manage.py createsuperuser
```

Then set that user's `role` to `admin` (via Django admin at `/admin-django/` or the shell).

### Quick demo: example dataset

Instead of creating users and courses by hand, load the ready-made demo
environment (3 courses, admin + 2 assistants + 8 students with barcodes,
analysis sheets in open/too-early/too-late windows, and a few graded
submissions):

```bash
uv run python manage.py load_examples --reset
```

All demo accounts share the password `FlameCheck-Demo-123` (log in as
`admin`, `assistant.bio`, or `student-david`). Then verify the whole app over
live HTTP with the end-to-end checker (54 checks):

```bash
uv run python examples/verify_demo.py
```

See [`examples/README.md`](../examples/README.md) for the full dataset layout,
the per-student sheet design, and what to try.

### Staging demo: factory-based seeder

For a staging environment you can seed a rich demo dataset directly from the
factory modules (the same `factory.py` definitions the test-suite uses),
instead of the fixed JSON files behind `load_examples`. The command builds
everything programmatically so the demo layout lives in code and is easy to
tweak:

```bash
uv run python manage.py seed_demo --reset
```

It creates:

* the ion / substance reference catalog (extended cation/anion scope), plus the
  salts from `examples/substance_list.csv` for the Geology course,
* **5 courses** (Chemistry / Biology / Geology / Medicine / Materials), Geology
  being the *active* (default) course,
* **21 users** — an admin, five assistants (one per course) and fifteen
  students (three per course, each with an integer `labspace_id` 1–3) — **all
  sharing the password `FlameCheck32!`**, plus a barcode for every student,
* **12 analysis types** (a shared set, a simple Medicine set and the full
  Geology task programme Practice + Analysis 1–5), with **analysis instances**
  fanned out one-per-student per announcement — each labelled
  `<type name, no spaces>_<labspace_id>` (e.g. `Cations1_1`) — and time
  windows spanning the *open*, *too early*, *too late* and *submitted* states,
* **student → instance assignments** (the per-student sheet design). The
  Geology answer keys are the union of the ions of a few of the CSV salts,
  restricted to each analysis' scope,
* the singleton `GradingConfig` **and** per-course overrides: Geology
  (per-analysis, all-or-nothing with a −2 / −4 retry penalty), Chemistry
  ("new analysis" repeat workflow with a 5-point retry deduction), Medicine
  (per-analysis, three trials) and Biology (per-ion, one attempt),
* the singleton `AppSettings` (active course), multiple-choice cards (flame
  test for Chemistry, basic acid/base/amino-acid/redox for Medicine and
  Biology, and the all-or-nothing European-Pharmacopoeia monograph card for
  Geology), and
* a handful of pre-seeded submissions graded through the real `submit()`
  business logic.

The command is **idempotent** — re-running it refreshes the demo rows without
duplicating them. `--reset` first wipes the seeded users, courses and the
analyses domain. Log in with any demo account and the password `FlameCheck32!`
(e.g. `admin`, `assistant.bio` or `student-anna`).

## 6. Run the development server

```bash
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000> for the app and <http://127.0.0.1:8000/api/v1/docs>
for the interactive OpenAPI documentation (DEBUG mode only).

## Production

Production runs the Django project under **Gunicorn** (WSGI) with **WhiteNoise**
serving the built frontend, selected via `DJANGO_SETTINGS_MODULE=flamecheck.settings.production`.
The **database is configurable through `.env`** and defaults to SQLite; point
`DATABASE_URL` at a `postgres://` URL to use PostgreSQL.

```bash
# Configure the environment
cp .env-template .env
#   -> set ENV=production, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS,
#      and DATABASE_URL if you want PostgreSQL.

# SQLite (default, single container):
docker compose -f docker/docker-compose.dev-full.yaml up --build -d

# PostgreSQL (opt-in): install the driver and activate the profile
uv sync --extra postgres
docker compose -f docker/docker-compose.dev-full.yaml --profile postgres up --build -d
```

The entrypoint (`docker/entrypoint.production.sh`) runs `migrate` +
`collectstatic` and then Gunicorn; it is engine-agnostic. Put a TLS-terminating
reverse proxy (Nginx / Caddy) in front of the container.

## Running the tests

```bash
uv run pytest
```
