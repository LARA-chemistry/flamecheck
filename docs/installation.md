(installation)=

# Installation

FlameCheck is a Django web application. It uses [`uv`](https://docs.astral.sh/uv/)
for Python dependency management and Node.js/Vite for the frontend.

This chapter covers:

- running it **locally** for development (SQLite by default),
- running it with **Docker** — production, staging, development and the
  dev-full-stack variants — with **SQLite or PostgreSQL**,
- the e-mail notification safety switch.

## Prerequisites

- Python 3.13
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20+ (only for developing/building the frontend)
- Docker + Docker Compose (only for the containerised variants)

**No database is required to start.** The default backend is **SQLite** (a
`db.sqlite3` file at the repository root). **PostgreSQL is optional** and is
selected by setting `DATABASE_URL` in `.env` (see [Choosing the database](#choosing-the-database-sqlite-vs-postgresql)).

## Local development

### 1. Get the code

```bash
git clone <repository-url> flamecheck
cd flamecheck
```

### 2. Install the Python environment

```bash
uv sync
```

This creates a virtual environment in `.venv/` and installs all dependencies
from `pyproject.toml` (the Django project plus the `users`, `substances`,
`analyses`, `config` and `multichoice` workspace packages).

### 3. Configure the environment (optional)

Everything works out of the box with the defaults (SQLite, development mode),
so this step can be skipped for a quick local run. To customise, copy the
template and edit it:

```bash
cp .env-template .env
```

The template documents every variable. The most relevant for the database:

```ini
# SQLite (default — uncomment or leave unset):
#DATABASE_URL=sqlite:///db.sqlite3

# PostgreSQL (opt-in; install the driver first with `uv sync --extra postgres`):
#DATABASE_URL=postgres://flamecheck:flamecheck@localhost:5432/flamecheck
```

`django-environ` parses `DATABASE_URL` and maps it to Django's `DATABASES`, so
switching engines requires no code or migration changes.

### 4. Build the frontend

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

This emits the built Vue app into `frontend/dist/`, which Django serves for
all non-API routes. For live-reloading development use
`npm --prefix frontend run dev` (which proxies `/api` to the Django dev server
on port 8000).

### 5. Create the database schema and seed data

```bash
uv run python manage.py migrate
uv run python manage.py import_catalog      # loads the ion + substance catalog
uv run python manage.py init_barcode        # (optional) create a test student barcode
```

Create an initial admin user:

```bash
uv run python manage.py init_admin
```

`init_admin` reads `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_MAIL` /
`DJANGO_SUPERUSER_PASSWORD` from `.env` and creates the user when no users
exist yet. Then set that user's `role` to `admin` (via Django admin at
`/admin-django/` or the shell):

```bash
uv run python manage.py shell -c \
  "from users.models import User; User.objects.filter(username='admin').update(role='admin')"
```

### 6. (Optional) Load a demo dataset

There are two demo seeder commands:

**`seed_demo` — the factory-based demo (recommended).** It builds a rich,
close-to-reality dataset programmatically (the same factory definitions the
test suite uses):

```bash
uv run python manage.py seed_demo --reset
```

It creates:

* the ion / substance reference catalog, plus the salts from
  `examples/substance_list.csv` for the Geology course,
* **5 courses** (Chemistry / Biology / Geology / Medicine / Materials), Geology
  being the *active* (default) course,
* **21 users** — an admin, five assistants (one per course) and fifteen
  students (three per course, each with an integer `labspace_id` 1–3) — **all
  sharing the password `FlameCheck32!`** — plus a barcode for every student,
* **12 analysis types** and per-student analysis instances (each labelled
  `<type name, no spaces>_<labspace_id>`) with time windows spanning the
  *open*, *too early*, *too late* and *submitted* states,
* the singleton `GradingConfig` **and** per-course overrides (per-analysis
  scoring, "new analysis" retry workflow, per-ion single attempts, …),
* multiple-choice cards (flame test, basic acid/base/amino-acid/redox, and the
  all-or-nothing European-Pharmacopoeia monograph card), and
* a handful of pre-seeded submissions graded through the real `submit()`
  business logic.

The command is **idempotent** — re-running it refreshes the demo rows without
duplicating them. `--reset` first wipes the seeded users, courses and the
analyses domain.

**`load_examples` — the JSON examples dataset.** A smaller, file-driven demo
(3 courses, admin + 2 assistants + 8 students with barcodes, a few graded
submissions; all accounts share the password `FlameCheck-Demo-123`):

```bash
uv run python manage.py load_examples --reset
```

Then verify the whole app over live HTTP with the end-to-end checker:

```bash
uv run python examples/verify_demo.py
```

See the `examples/README.md` file in the repository for the dataset layout and
what to try.

### 7. Run the development server

```bash
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000> for the app and <http://127.0.0.1:8000/api/v1/docs>
for the interactive OpenAPI documentation (DEBUG mode only).

---

## Docker

Four compose files ship in the repository:

| File | Purpose | Settings module | Port | Demo data |
|------|---------|-----------------|------|-----------|
| `docker-compose.yaml` | **Production** (single app container) | `production` | 8000 | none |
| `docker-compose-staging.yaml` | **Staging** (production image + debug) | `production` | 8001 | seeded on boot (`SEED_DEMO`) |
| `docker-compose-dev.yaml` | **Development** (autoreloading server) | `development` | 8000 | none |
| `docker/docker-compose.dev-full.yaml` | **Dev full stack** (dev server + Postgres) | `development` | 8000 | none |

All of them read a `.env` file (copy `.env-template` to `.env` first). The
image is built from `docker/Dockerfile` — a multi-stage build that compiles the
frontend, installs the Python project with `uv`, and assembles a slim
runtime image (non-root user, `gnupg` included for the PGP e-mails).

### Production (SQLite — default)

A single container, no external services:

```bash
cp .env-template .env
#   -> set ENV=production, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS.

docker compose -f docker-compose.yaml --env-file .env up --build -d
```

The SQLite database, collected static files and uploaded media live in named
volumes (`flamecheck_db`, `flamecheck_static`, `flamecheck_media`), so they
survive `up`/`down` cycles. The entrypoint runs `migrate` + `collectstatic`
and starts Gunicorn (`GUNICORN_WORKERS`, default 3).

### Production (PostgreSQL — opt-in)

The same compose file contains an optional `postgres:16-alpine` service behind
the `postgres` profile:

```bash
cp .env-template .env
#   -> set ENV=production, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS and:
#      DATABASE_URL=postgres://flamecheck:flamecheck@db:5432/flamecheck
#      (POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD default to "flamecheck")
#   -> install the driver for local tooling:
uv sync --extra postgres

docker compose -f docker-compose.yaml --env-file .env --profile postgres up --build -d
```

The app waits for the database to become healthy before starting
(`depends_on: db: condition: service_healthy`). The Postgres data lives in the
`db_data` volume.

### Staging

`docker-compose-staging.yaml` runs the **production image** (pulled from the
GitLab registry) with debugging enabled, on port 8001, and **seeds the demo
dataset on boot** (see [§6](#6-optional-load-a-demo-dataset) for what it
contains; every demo account shares the password `FlameCheck32!`):

```bash
cp .env-template .env
#   -> set DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS (and APP_PORT if needed).

docker compose -f docker-compose-staging.yaml --env-file .env up -d --build

# Wipe + re-seed the demo dataset:
SEED_DEMO=reset docker compose -f docker-compose-staging.yaml --env-file .env up -d --build
```

Seeding is controlled by `SEED_DEMO` (default `true` in this compose):
`true` re-seeds idempotently, `reset` wipes and re-seeds, an empty value
(`SEED_DEMO=`) skips it.

### Development

`docker-compose-dev.yaml` runs the **development** settings module
(`DJANGO_DEBUG=true`, autoreloading dev server, DEBUG-only OpenAPI docs) on
port 8000:

```bash
cp .env-template .env
docker compose -f docker-compose-dev.yaml --env-file .env up --build -d
```

### Dev full stack

`docker/docker-compose.dev-full.yaml` is the development setup with a
**PostgreSQL** container (`postgres:16-alpine`, published on port 5432) and a
matching `DATABASE_URL`:

```bash
cp .env-template .env
#   -> DATABASE_URL=postgres://flamecheck:flamecheck@postgres:5432/flamecheck
docker compose -f docker/docker-compose.dev-full.yaml --env-file .env up --build -d
```

Useful day-2 commands:

```bash
docker compose -f docker-compose.yaml --env-file .env exec flamecheck python manage.py shell
docker compose -f docker-compose.yaml --env-file .env logs -f flamecheck
docker compose -f docker-compose.yaml --env-file .env down
```

For how to run the stack in a real production environment — reverse proxy,
TLS, load-balancing, backups, scaling — see
{ref}`Deployment <deployment>`.

---

## Choosing the database: SQLite vs. PostgreSQL

Both engines run the exact same code; the choice is made entirely through
`DATABASE_URL` (see the `.env-template` for the URL syntax, including MySQL).

| | **SQLite** (default) | **PostgreSQL** |
|---|---|---|
| External service | none | `postgres:16-alpine` container (or an external instance) |
| Storage | one file (`/opt/db/db.sqlite3` in Docker) | `db_data` volume (or your DBA's) |
| Concurrency | single-writer; fine for a class of tens/hundreds of students | full multi-writer; for many courses / high traffic |
| Backups | built-in online backup feature (admin Settings → Database) | `pg_dump` |
| When to use | teaching labs, pilots, demo/staging | several courses in parallel, larger student bodies |

SQLite is deliberately the zero-dependency default: a lab with one course and a
few hundred students runs comfortably on it. If you outgrow it (or want
point-in-time recovery), move to PostgreSQL — set `DATABASE_URL` on an empty
deployment and the entrypoint's `migrate` creates the schema. Migrating an
existing SQLite database is a one-off export/import (`pgloader` or
`pg_dump`-style copy via the Django ORM); for a fresh deployment there is
nothing else to do.

> **Note:** the in-app backup/restore feature (admin Settings → Database) is
> implemented for SQLite. With PostgreSQL, take `pg_dump` snapshots of the
> `db_data` volume instead (see {ref}`Deployment <deployment>`).

---

## E-mail notifications (submission confirmations)

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

---

## Running the tests

```bash
uv run pytest
```
