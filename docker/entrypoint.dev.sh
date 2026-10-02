#!/bin/sh
set -e

# The virtualenv lives at /opt/.venv and is already on PATH (set in the
# Dockerfile). Use the binaries directly rather than `uv run`.

# Database backend is engine-agnostic: whatever DATABASE_URL points at
# (SQLite by default, or PostgreSQL when set). Migrations work for both.
python manage.py migrate --noinput
# Self-heal a corrupt migration state (recorded-but-never-applied DDL) so a
# stale dev database does not crash the first request.
python manage.py check_migrations

# Collect static files so the built frontend is served via WhiteNoise.
python manage.py collectstatic --noinput

# Run the development server (reloads on change).
exec python manage.py runserver 0.0.0.0:8000
