"""
Self-heal a corrupt migration state before the app serves requests.

A prior crashed or partially-applied ``migrate`` can leave the database in a
state where ``django_migrations`` records a migration as applied even though
part of its DDL never ran. ``manage.py migrate`` then reports "No migrations to
apply" (it trusts the records) while the schema is still missing columns, so the
next step that touches those columns crashes (e.g. ``seed_demo`` failing with
``no such column: analyses_analysistype.default_window_start``).

This command reconciles the two sides. For every migration recorded as applied
it checks that the columns the migration adds actually exist in the database.
When a missing column is found, the recorded state and the real schema disagree,
so the affected migration rows are deleted and ``migrate`` is re-run, which
re-applies the now-"pending" migrations on top of the existing schema (an
``AddField`` is a no-op for a column that already exists).

The check is engine-agnostic (SQLite and PostgreSQL) and only inspects columns
added by ``AddField`` operations - the class of migration that can be left
half-applied. It never drops data.
"""

from __future__ import annotations

import argparse
import logging

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.fields import AddField
from django.db.models import ForeignKey, ManyToManyField, OneToOneField

logger = logging.getLogger("flamecheck.migrations")


class Command(BaseCommand):
    """Verify applied migrations match the schema; re-apply any that are missing."""

    help = (
        "Check that every applied migration's columns exist in the database; "
        "if a recorded migration's DDL is missing, unapply its record and "
        "re-run `migrate` to reconcile the schema."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register the ``--check`` option (exit non-zero when a repair is needed)."""
        parser.add_argument(
            "--check",
            action="store_true",
            help="Only detect; exit with status 1 if a repair would be needed (no changes).",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Reconcile the recorded migration state with the actual schema."""
        loader = MigrationLoader(connection)
        applied = set(loader.applied_migrations)
        if not applied:
            self.stdout.write(self.style.NOTICE("No applied migrations; nothing to check."))
            return

        missing: dict[tuple[str, str], list[str]] = {}
        all_columns = self._all_db_columns()
        for app_label, name in applied:
            migration = loader.disk_migrations.get((app_label, name))
            if migration is None:
                continue
            for column in self._added_columns(migration):
                if column is not None and column not in all_columns:
                    missing.setdefault((app_label, name), []).append(column)
            if (app_label, name) in missing:
                missing[(app_label, name)] = sorted(missing[(app_label, name)])

        if not missing:
            self.stdout.write(self.style.SUCCESS("Migration state matches the schema; nothing to do."))
            return

        for (app_label, name), columns in sorted(missing.items()):
            self.stdout.write(
                self.style.WARNING(f"Applied migration {app_label}.{name} is missing column(s): {', '.join(columns)}")
            )

        if options["check"]:
            from django.core.management.base import CommandError

            raise CommandError("Schema out of sync with recorded migrations (re-run without --check to repair).")

        self.stdout.write(self.style.WARNING("Unapplying the out-of-date records and re-running `migrate`..."))
        self._unapply_records(missing)
        self._remigrate()
        self.stdout.write(self.style.SUCCESS("Re-applied pending migrations; schema is now in sync."))

    def _remigrate(self) -> None:
        """
        Re-run ``migrate`` to apply the now-pending migrations.

        Wrapped so that SQLite foreign-key constraint checks are suspended for
        the duration: re-applying an ``AddField`` is a schema change, and
        SQLite's schema editor refuses to run while FK checks are enabled inside
        a (possibly outer, e.g. pytest) atomic transaction.
        """
        from django.core.management import call_command

        supports = connection.features.can_defer_constraint_checks
        if supports:
            connection.disable_constraint_checking()
        try:
            call_command("migrate", interactive=False, verbosity=1)
        finally:
            if supports:
                connection.enable_constraint_checking()

    # -- helpers -------------------------------------------------------------
    def _all_db_columns(self) -> set[str]:
        """Return the set of every column name in the database (across tables)."""
        columns: set[str] = set()
        with connection.cursor() as cursor:
            for table in connection.introspection.table_names(cursor):
                for col in connection.introspection.get_table_description(cursor, table):
                    columns.add(col.name)
        return columns

    def _added_columns(self, migration) -> set[str | None]:
        """
        Return the DB column name(s) this migration adds, one per ``AddField``.

        A plain field maps to its own column; a ``ForeignKey``/``OneToOneField``
        maps to ``<name>_id``; a ``ManyToManyField`` creates an intermediate
        table rather than a column on the parent, so it is skipped (``None``).
        """
        columns: set[str | None] = set()
        for operation in migration.operations:
            # Only ``AddField`` creates a new column. ``AlterField`` /
            # ``RemoveField`` also subclass FieldOperation but do not add one.
            if not isinstance(operation, AddField):
                continue
            field_name = operation.name
            field = operation.field
            if isinstance(field, ManyToManyField):
                columns.add(None)  # intermediate table; no parent column to check
            elif isinstance(field, (ForeignKey, OneToOneField)):
                columns.add(f"{field_name}_id")
            else:
                columns.add(field_name)
        return columns

    def _unapply_records(self, missing: dict[tuple[str, str], list[str]]) -> None:
        """Delete the ``django_migrations`` rows for the out-of-date migrations."""
        with connection.cursor() as cursor:
            for app_label, name in missing:
                cursor.execute("DELETE FROM django_migrations WHERE app = %s AND name = %s", [app_label, name])
