#!/bin/sh
set -e

# Apply database migrations
uv run python manage.py migrate --noinput

# Collect static files
uv run python manage.py collectstatic --noinput

# Start the application server
exec uv run gunicorn flamecheck.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
