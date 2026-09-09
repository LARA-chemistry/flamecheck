(installation)=

# Installation

FlameCheck is a Django web application. It uses [`uv`](https://docs.astral.sh/uv/) for
Python dependency management and Node.js/Vite for the frontend.

## Prerequisites

- Python 3.13
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20+ (only for developing/building the frontend)
- A PostgreSQL database (or SQLite for local development)

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

## 3. Configure the environment

Copy the example settings file and adjust as needed:

```bash
cp .env-template .env
```

At minimum, set the database connection and the secret key. For local
development the project defaults to SQLite, so you can skip this step.

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

Then set that user's `role` to `admin` (via Django admin at `/admin/` or the shell).

## 6. Run the development server

```bash
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000> for the app and <http://127.0.0.1:8000/api/v1/docs>
for the interactive OpenAPI documentation (DEBUG mode only).

## Running the tests

```bash
uv run pytest
```
