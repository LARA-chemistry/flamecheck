import contextlib
import logging

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("flamecheck.cache")


class UsersConfig(AppConfig):
    name = "users"
    verbose_name = _("Users")

    def ready(self):
        with contextlib.suppress(ImportError):
            import users.signals  # noqa: F401
        self._ensure_cache_table()

    @staticmethod
    def _ensure_cache_table() -> None:
        """
        Ensure the database cache table exists (idempotent bootstrap).

        The rate limits (login, barcode, registration) are backed by the
        *database* cache so they apply across all gunicorn workers. Django
        does not create that table automatically (the ``createcachetable``
        management command does), so we create it at app startup — keeping
        dev servers and container boots working without an extra manual
        step. The schema mirrors ``createcachetable``.
        """
        from django.conf import settings
        from django.core.cache import caches
        from django.core.cache.backends.db import BaseDatabaseCache
        from django.db import DatabaseError, connections
        from django.db import models as dj_models

        conn = connections["default"]
        for alias in settings.CACHES:
            cache = caches[alias]
            if not isinstance(cache, BaseDatabaseCache):
                continue
            table = cache._table
            if table in conn.introspection.table_names():
                continue
            qn = conn.ops.quote_name
            fields = (
                dj_models.CharField(name="cache_key", max_length=255),
                dj_models.TextField(name="value"),
                dj_models.DateTimeField(name="expires"),
            )
            try:
                with conn.cursor() as cursor:
                    column_defs = ", ".join(
                        f"{qn(f.name)} {f.db_type(connection=conn)}" + (" PRIMARY KEY" if f.name == "cache_key" else "")
                        for f in fields
                    )
                    cursor.execute(f"CREATE TABLE {qn(table)} ({column_defs})")
                    cursor.execute(f"CREATE INDEX {qn(f'{table}_expires')} ON {qn(table)} ({qn('expires')})")
                logger.info("Created database cache table %r", table)
            except DatabaseError:
                # Another process (e.g. a sibling gunicorn worker) created the
                # table in the meantime — nothing to do.
                logger.debug("Cache table %r already exists", table, exc_info=True)
