import logging
import os
import threading
import time

from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("flamecheck.backup")

_scheduler_started = False


def _start_backup_scheduler() -> None:
    """
    Start the in-process database-backup scheduler (once per process).

    A daemon thread polls the AppSettings singleton and runs a backup when the
    configured interval has elapsed. Concurrent processes (e.g. multiple
    gunicorn workers) can only produce duplicate backup files, never a
    corrupt state.
    """
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    from django.db import connection

    from config.db_backup import SCHEDULER_POLL_SECONDS, BackupError, run_if_due

    def _loop() -> None:
        while True:
            try:
                run_if_due()
            except BackupError:
                logger.exception("Scheduled database backup failed")
            except Exception:
                logger.exception("Unexpected error in the backup scheduler")
            finally:
                connection.close()
            time.sleep(SCHEDULER_POLL_SECONDS)

    threading.Thread(target=_loop, name="db-backup-scheduler", daemon=True).start()
    logger.info("Database backup scheduler started (poll every %ss)", SCHEDULER_POLL_SECONDS)


class ConfigConfig(AppConfig):
    """FlameCheck configuration app (courses, grading settings, database backups)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "config"
    verbose_name = _("Configuration")

    def ready(self) -> None:
        """Start the in-process backup scheduler (see settings.DATABASE_BACKUP_SCHEDULER)."""
        if not getattr(settings, "DATABASE_BACKUP_SCHEDULER", False):
            return
        # Under ``runserver`` the reloader spawns a child process; only the
        # child (WERKZEUG_RUN_MAIN=true) may start the scheduler thread.
        if settings.DEBUG and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            return
        _start_backup_scheduler()
