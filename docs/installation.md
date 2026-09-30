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
