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
so the missing columns are re-added directly through the schema editor. The
migration records are left untouched (deleting a record and re-running
``migrate`` would break the dependency chain once a later applied migration
depends on the repaired one).

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
        "if a recorded migration's DDL is missing, re-add the missing columns "
        "to reconcile the schema."
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

        self.stdout.write(self.style.WARNING("Re-adding the missing columns..."))
        self._repair(missing, loader)
        self.stdout.write(self.style.SUCCESS("Schema is now in sync with the recorded migrations."))

    def _repair(self, missing: dict[tuple[str, str], list[str]], loader: MigrationLoader) -> None:
        """
        Re-add the missing columns for each out-of-sync migration.

        Rather than deleting the migration record and re-running ``migrate``
        (which breaks the dependency chain when a *later* applied migration
        depends on the one being repaired), the missing columns are added
        directly through the schema editor. The migration record is left
        untouched, so the recorded history stays consistent.

        SQLite foreign-key checks are suspended for the schema changes.
        """
        from django.apps import apps as django_apps

        supports = connection.features.can_defer_constraint_checks
        if supports:
            connection.disable_constraint_checking()
        try:
            for (app_label, name), missing_columns in sorted(missing.items()):
                migration = loader.disk_migrations[(app_label, name)]
                self._reapply_missing_columns(app_label, migration, missing_columns, django_apps)
        finally:
            if supports:
                connection.enable_constraint_checking()

    @staticmethod
    def _reapply_missing_columns(app_label: str, migration, missing_columns: list[str], django_apps) -> None:
        """
        Add back only the columns in ``missing_columns`` from the migration.

        The model class is resolved from the ``AddField``'s ``model_name`` and
        the cloned field is rebound to it (a migration field is otherwise
        unbound), which is what ``schema_editor.add_field`` requires.
        """
        add_fields = [op for op in migration.operations if isinstance(op, AddField)]
        with connection.schema_editor() as schema_editor:
            for column in missing_columns:
                operation = next((op for op in add_fields if Command._column_for_field(op) == column), None)
                if operation is None:
                    # M2M intermediate tables are not re-created here (rare in a
                    # half-applied AddField); skip so the rest still reconcile.
                    continue
                model = django_apps.get_model(app_label, operation.model_name)
                # Idempotency guard: if the column is already present (e.g. the
                # drop in a test / a concurrent change did not take effect in
                # this connection's view), skip it instead of duplicating.
                if Command._column_exists(model, column):
                    continue
                field = operation.field.clone()
                # A migration field is unbound: set its name/column/concrete
                # (normally done during model-class construction) and bind the
                # model, which ``schema_editor.add_field`` requires.
                field.set_attributes_from_name(operation.name)
                field.model = model
                schema_editor.add_field(model, field)

    @staticmethod
    def _column_exists(model, column: str) -> bool:
        """True if ``column`` is present on ``model``'s table right now."""
        table = model._meta.db_table
        with connection.cursor() as cursor:
            try:
                columns = connection.introspection.get_table_description(cursor, table)
            except Exception:  # pragma: no cover - table vanished mid-flight
                return False
        return any(col.name == column for col in columns)

    @staticmethod
    def _column_for_field(operation: AddField) -> str | None:
        """DB column name for an ``AddField`` (FK/1-1 -> ``<name>_id``)."""
        if isinstance(operation.field, ManyToManyField):
            return None
        if isinstance(operation.field, (ForeignKey, OneToOneField)):
            return f"{operation.name}_id"
        return operation.name

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
            columns.add(self._column_for_field(operation))
        return columns
