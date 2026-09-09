"""ASGI config for the FlameCheck project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flamecheck.settings")

application = get_asgi_application()
