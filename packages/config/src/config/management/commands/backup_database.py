"""One-shot database backup management command (usable from cron/systemd timers)."""

from __future__ import annotations

import argparse

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from config.db_backup import BackupError, resolve_backup_location, run_backup
from config.models import AppSettings


class Command(BaseCommand):
    """Take one consistent backup of the database."""

    help = "Take a consistent SQLite backup of the database."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register the ``--location`` and ``--keep`` options."""
        parser.add_argument(
            "--location",
            default=None,
            help="Backup directory (default: the configured backup_location).",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=None,
            help="Number of backups to keep (default: the configured backup_keep).",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Take one backup and record it on the AppSettings singleton."""
        s = AppSettings.get_instance()
        location = (
            resolve_backup_location(options["location"])
            if options["location"]
            else resolve_backup_location(s.backup_location)
        )
        keep = options["keep"] if options["keep"] is not None else s.backup_keep
        try:
            result = run_backup(location, keep)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        s.last_backup_at = timezone.now()
        s.last_backup_file = result["file"]
        s.save(update_fields=["last_backup_at", "last_backup_file"])
        self.stdout.write(self.style.SUCCESS(f"Backup written to {result['path']} ({result['size']} bytes)"))
