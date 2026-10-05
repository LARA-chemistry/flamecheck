"""Tests for the ``check_migrations`` self-healing command."""

from __future__ import annotations

import io

import pytest
from config.management.commands.check_migrations import Command as CheckMigrationsCommand
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.operations.fields import AddField
from django.db.models import Field

pytestmark = pytest.mark.django_db


def _has_column(table: str, column: str) -> bool:
    """True if ``table`` has a column named ``column`` (fresh introspection)."""
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
        return any(col.name == column for col in description)


def _drop_supported(table: str, column: str) -> bool:
    """
    Drop ``column`` and report whether the drop actually took effect.

    ``ALTER TABLE ... DROP COLUMN`` needs SQLite >= 3.35. If the statement
    raises (older SQLite) or the column is still visible to introspection
    (some builds do not reflect in-transaction DDL to a fresh query), we report
    False so the caller can skip rather than fail confusingly.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    except Exception:
        return False
    # Re-read on a fresh cursor; if the DDL is not yet visible, the check will
    # report the column still present and we skip.
    return not _has_column(table, column)


skip_if_no_drop = pytest.mark.skip(reason="SQLite backend does not support ALTER TABLE ... DROP COLUMN")


# The repair performs a real schema change (re-applying an ``AddField``), which
# on SQLite cannot run inside an atomic transaction. Those tests therefore use a
# real (non-atomic) transaction via ``django_db(transaction=True)``; read-only
# checks run under the default per-test atomic block.
class TestCheckMigrations:
    """The command reconciles recorded migration state with the real schema."""

    def test_clean_db_reports_nothing_to_do(self) -> None:
        """A consistent database produces a no-op with a success message."""
        stream = io.StringIO()
        call_command("check_migrations", stdout=stream)
        assert "nothing to do" in stream.getvalue()

    def test_check_mode_exits_when_schema_is_out_of_sync(self) -> None:
        """``--check`` raises CommandError without modifying the database."""
        if not _drop_supported("config_appsettings", "active_course_id"):
            pytest.skip("DROP COLUMN unavailable in this SQLite build")
        # The config 0002 migration is still recorded as applied; only its DDL is gone.
        with pytest.raises(CommandError):
            call_command("check_migrations", check=True)
        # --check must not have repaired anything.
        assert not _has_column("config_appsettings", "active_course_id")

    @pytest.mark.django_db(transaction=True)
    def test_repair_reapplies_missing_columns(self) -> None:
        """Without ``--check`` the missing columns are re-created."""
        # Drop every column the config 0002 migration adds (all FKs), so the
        # repair is a clean whole-migration re-apply (as in the real corruption).
        for table, col in (
            ("config_assistantcourse", "assistant_id"),
            ("config_assistantcourse", "course_id"),
            ("config_appsettings", "active_course_id"),
            ("config_gradingconfig", "course_id"),
        ):
            if not _drop_supported(table, col):
                pytest.skip("DROP COLUMN unavailable in this SQLite build")
        call_command("check_migrations")
        assert _has_column("config_appsettings", "active_course_id")
        assert _has_column("config_gradingconfig", "course_id")

    @pytest.mark.django_db(transaction=True)
    def test_repair_is_idempotent_on_a_clean_db(self) -> None:
        """Running the repair twice on a consistent DB is a no-op."""
        call_command("check_migrations")
        call_command("check_migrations")  # second run must not raise
        assert _has_column("config_appsettings", "backup_enabled")

    @pytest.mark.django_db(transaction=True)
    def test_repair_restores_a_corrupt_analyses_schema(self) -> None:
        """A half-applied analyses 0002 (FK columns missing) is re-applied."""
        for table, col in (
            ("analyses_analysisinstance", "course_id"),
            ("analyses_analysisnotification", "course_id"),
            ("analyses_analysisnotification", "instance_id"),
        ):
            if not _drop_supported(table, col):
                pytest.skip("DROP COLUMN unavailable in this SQLite build")
        call_command("check_migrations")
        assert _has_column("analyses_analysisinstance", "course_id")
        assert _has_column("analyses_analysisnotification", "instance_id")


class TestAddedColumnsHelper:
    """
    The ``AddField`` -> DB-column mapping is correct for every field kind.

    These tests exercise the detection logic directly (no DDL), so they run on
    any SQLite build.
    """

    def _cmd(self) -> CheckMigrationsCommand:
        return CheckMigrationsCommand()

    def _migration_with(self, *ops) -> object:
        return type("Migration", (), {"operations": list(ops)})()

    def test_plain_field_maps_to_its_name(self) -> None:
        op = AddField("analysistype", "default_window_start", Field())
        assert self._cmd()._added_columns(self._migration_with(op)) == {"default_window_start"}

    def test_foreign_key_maps_to_id_column(self) -> None:
        from django.db import models

        op = AddField("analysisinstance", "student", models.ForeignKey("users.User", on_delete=models.CASCADE))
        assert self._cmd()._added_columns(self._migration_with(op)) == {"student_id"}

    def test_many_to_many_is_skipped(self) -> None:
        from django.db import models

        op = AddField("analysisinstance", "assigned_substances", models.ManyToManyField("substances.Ion"))
        # M2M creates an intermediate table, not a parent column -> None.
        assert self._cmd()._added_columns(self._migration_with(op)) == {None}
