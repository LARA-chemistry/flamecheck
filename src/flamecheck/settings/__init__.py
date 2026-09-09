"""
FlameCheck settings package.

The default settings module points at development settings; production and
test settings are selected by setting ``DJANGO_SETTINGS_MODULE`` accordingly
(e.g. ``flamecheck.settings.production``).
"""

from .development import *  # noqa: F403
