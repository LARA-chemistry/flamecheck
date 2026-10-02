"""Restore the database from a backup file (management command)."""

from __future__ import annotations

import argparse

from django.core.management.base import BaseCommand, CommandError

from config.db_backup import BackupError, mark_restored, resolve_backup_location, restore_backup
from config.models import AppSettings


class Command(BaseCommand):
    """Restore the database from a backup file."""

    help = "Restore the SQLite database from a backup file (the server should be stopped or restarted afterwards)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register the ``filename`` positional and the ``--location`` option."""
        parser.add_argument("filename", help="Backup file name (as listed by the Database section).")
        parser.add_argument(
            "--location",
            default=None,
            help="Backup directory (default: the configured backup_location).",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Restore the database from the given backup file."""
        s = AppSettings.get_instance()
        location = (
            resolve_backup_location(options["location"])
            if options["location"]
            else resolve_backup_location(s.backup_location)
        )
        try:
            result = restore_backup(location, options["filename"])
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        mark_restored(result["file"])
        self.stdout.write(
            self.style.SUCCESS(f"Database restored from {result['path']}. Restart the server for full consistency.")
        )
