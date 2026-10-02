"""Tests for the ``check_migrations`` self-healing command."""

from __future__ import annotations

import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

pytestmark = pytest.mark.django_db


def _has_column(table: str, column: str) -> bool:
    """True if ``table`` has a column named ``column``."""
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
        return any(col.name == column for col in description)


def _drop_column(table: str, column: str) -> None:
    """Drop ``column`` from ``table`` (SQLite ``ALTER TABLE ... DROP COLUMN``)."""
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


# The repair performs a real schema change (re-applying an ``AddField``), which
# on SQLite cannot run inside an atomic transaction. These tests therefore use a
# real (non-atomic) transaction via ``django_db(transaction=True)``; the read-only
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
        # Simulate a crashed/partial migration: the analyses 0005 AddField columns
        # are gone, but the migration is still recorded as applied.
        _drop_column("analyses_analysistype", "default_window_start")
        _drop_column("analyses_analysistype", "default_window_end")

        with pytest.raises(CommandError):
            call_command("check_migrations", check=True)

        # --check must not have repaired anything.
        assert not _has_column("analyses_analysistype", "default_window_start")

    @pytest.mark.django_db(transaction=True)
    def test_repair_reapplies_missing_columns(self) -> None:
        """Without ``--check`` the missing columns are re-created."""
        _drop_column("config_appsettings", "backup_enabled")

        call_command("check_migrations")

        assert _has_column("config_appsettings", "backup_enabled")

    @pytest.mark.django_db(transaction=True)
    def test_repair_is_idempotent_on_a_clean_db(self) -> None:
        """Running the repair twice on a consistent DB is a no-op."""
        call_command("check_migrations")
        call_command("check_migrations")  # second run must not raise
        assert _has_column("config_appsettings", "backup_enabled")

    @pytest.mark.django_db(transaction=True)
    def test_repair_restores_a_corrupt_analyses_schema(self) -> None:
        """The exact staging failure: analyses 0005 columns missing but recorded."""
        _drop_column("analyses_analysistype", "default_window_start")
        _drop_column("analyses_analysistype", "default_window_end")

        call_command("check_migrations")

        assert _has_column("analyses_analysistype", "default_window_start")
        assert _has_column("analyses_analysistype", "default_window_end")
