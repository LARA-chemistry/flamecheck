#!/bin/sh
set -e

# Apply database migrations
uv run python manage.py migrate --noinput

# Run the development server (reloads on change)
exec uv run python manage.py runserver 0.0.0.0:8000
