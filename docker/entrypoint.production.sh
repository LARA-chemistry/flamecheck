#!/bin/sh
set -e

# The virtualenv lives at /opt/.venv and is already on PATH (set in the
# Dockerfile). Use the binaries directly rather than `uv run` (uv is only
# present in the build stage, not the final image).

# Apply database migrations (engine-agnostic: SQLite by default, or
# PostgreSQL when DATABASE_URL is set via .env — see .env-template).
python manage.py migrate --noinput

# Collect static files (including the built frontend served via WhiteNoise).
python manage.py collectstatic --noinput

# Start the application server.
exec gunicorn flamecheck.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
