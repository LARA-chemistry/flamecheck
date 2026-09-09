#!/bin/sh
set -e

# Database backend is engine-agnostic: it is whatever DATABASE_URL points at
# (SQLite by default, or PostgreSQL when set). Migrations work for both.
uv run python manage.py migrate --noinput

# Run the development server (reloads on change)
exec uv run python manage.py runserver 0.0.0.0:8000
