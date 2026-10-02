"""Tests for the database backup/restore service, endpoints, and scheduler."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from config.db_backup import (
    BackupError,
    BackupNotSupported,
    get_status,
    restore_backup,
    run_backup,
    run_if_due,
)
from config.models import AppSettings
from django.db import connections
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def backup_dir(tmp_path) -> Path:
    d = tmp_path / "backups"
    d.mkdir()
    return d


def _write_settings(**kwargs) -> AppSettings:
    s = AppSettings.get_instance()
    for k, v in kwargs.items():
        setattr(s, k, v)
    s.save()
    return s


class TestRunBackup:
    def test_creates_integrity_checked_snapshot(self, backup_dir, student):
        result = run_backup(backup_dir, keep=10)
        target = backup_dir / result["file"]
        assert target.exists()
        assert result["size"] == target.stat().st_size
        # The snapshot must be a valid SQLite DB containing our data.
        con = sqlite3.connect(str(target))
        try:
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            count = con.execute("SELECT COUNT(*) FROM users_user").fetchone()[0]
        finally:
            con.close()
        assert count >= 1  # the student fixture exists

    def test_snapshots_a_consistent_state(self, backup_dir, student):
        # A backup taken after a commit captures committed rows.
        result = run_backup(backup_dir, keep=10)
        con = sqlite3.connect(str(backup_dir / result["file"]))
        try:
            assert con.execute("SELECT COUNT(*) FROM users_user").fetchone()[0] >= 1
        finally:
            con.close()

    def test_prunes_old_managed_backups(self, backup_dir):
        for _ in range(4):
            run_backup(backup_dir, keep=2)
        managed = [p.name for p in backup_dir.glob("flamecheck-*.sqlite3")]
        assert len(managed) == 2

    def test_keeps_unmanaged_files(self, backup_dir):
        foreign = backup_dir / "my-own.sqlite3"
        foreign.write_bytes(b"x")
        run_backup(backup_dir, keep=1)
        assert foreign.exists()

    def test_non_sqlite_raises(self, backup_dir, monkeypatch):
        from django.db import connections

        monkeypatch.setattr(connections["default"], "vendor", "postgresql")
        with pytest.raises(BackupNotSupported):
            run_backup(backup_dir, keep=1)


class TestRestoreBackup:
    # NOTE: the file-swap restore tests live in ``tests/test_db_backup_restore.py``
    # (they re-point the test DB at a file, which is incompatible with the
    # in-memory DB used by the rest of this file).

    def test_missing_file_raises(self, backup_dir):
        # A missing file is rejected before any connection is touched.
        with pytest.raises(BackupError):
            restore_backup(backup_dir, "flamecheck-19700101-000000.sqlite3")

    def test_path_traversal_rejected(self, backup_dir, tmp_path):
        outside = tmp_path / "outside.sqlite3"
        outside.write_bytes(b"x")
        with pytest.raises(BackupError):
            restore_backup(backup_dir, "../outside.sqlite3")

    def test_non_sqlite_raises(self, backup_dir, monkeypatch):
        monkeypatch.setattr(connections["default"], "vendor", "postgresql")
        with pytest.raises(BackupNotSupported):
            restore_backup(backup_dir, "anything.sqlite3")

    def test_memory_db_relocates_to_file(self, backup_dir, student):
        # On an in-memory DB there is no file to swap; the connection is
        # relocated to a real file holding the restored data.
        result = run_backup(backup_dir, keep=10)
        restored = restore_backup(backup_dir, result["file"])
        assert connections["default"].settings_dict["NAME"] == restored["path"]

    def test_file_swap_replaces_live_file(self, tmp_path):
        """The file-swap helper atomically replaces a standalone file database."""
        from config.db_backup import _swap_file_database

        # Build a standalone file DB with a marker row (no Django models).
        live = tmp_path / "live.sqlite3"
        src = sqlite3.connect(str(live))
        src.execute("CREATE TABLE t (v TEXT)")
        src.execute("INSERT INTO t VALUES ('before')")
        src.commit()
        # Back it up to a snapshot file.
        snap = tmp_path / "snap.sqlite3"
        dst = sqlite3.connect(str(snap))
        src.backup(dst)
        dst.close()
        # Mutate the live DB, then swap in the snapshot.
        src.execute("INSERT INTO t VALUES ('after')")
        src.commit()

        _swap_file_database(None, live, snap)
        # The live file now holds only the pre-mutation row.
        check = sqlite3.connect(str(live))
        rows = [r[0] for r in check.execute("SELECT v FROM t").fetchall()]
        check.close()
        assert rows == ["before"]


class TestRunIfDue:
    def test_disabled_is_noop(self, backup_dir):
        _write_settings(backup_enabled=False, backup_location=str(backup_dir))
        assert run_if_due() is None

    def test_runs_when_never_backed_up(self, backup_dir):
        _write_settings(backup_enabled=True, backup_interval_minutes=60, backup_location=str(backup_dir))
        result = run_if_due()
        assert result is not None
        s = AppSettings.get_instance()
        assert s.last_backup_file == result["file"]
        assert s.last_backup_at is not None

    def test_skips_when_not_due(self, backup_dir):
        _write_settings(backup_enabled=True, backup_interval_minutes=60, backup_location=str(backup_dir))
        assert run_if_due() is not None
        assert run_if_due() is None  # second call immediately: not due

    def test_due_after_interval(self, backup_dir):
        _write_settings(backup_enabled=True, backup_interval_minutes=1, backup_location=str(backup_dir))
        assert run_if_due() is not None
        s = AppSettings.get_instance()
        s.last_backup_at = timezone.now() - timedelta(minutes=2)
        s.save()
        assert run_if_due() is not None


class TestGetStatus:
    def test_shape_and_backups(self, backup_dir, student):
        _write_settings(backup_enabled=True, backup_interval_minutes=15, backup_location=str(backup_dir))
        run_backup(backup_dir, keep=10)
        status = get_status()
        assert status["sqlite"] is True
        assert status["backend"] == "sqlite"
        assert status["enabled"] is True
        assert status["interval_minutes"] == 15
        assert status["keep"] == 10
        assert len(status["backups"]) == 1
        assert status["backups"][0]["file"].startswith("flamecheck-")


class TestApi:
    def test_requires_admin(self, client, student, auth_headers):
        assert client.get("/api/v1/admin/database/backups", **auth_headers(student)).status_code == 403

    def test_status_endpoint(self, client, admin_user, auth_headers):
        resp = client.get("/api/v1/admin/database/backups", **auth_headers(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["sqlite"] is True
        assert "backups" in body

    def test_backup_now_endpoint(self, client, admin_user, auth_headers, tmp_path):
        _write_settings(backup_location=str(tmp_path))
        resp = client.post("/api/v1/admin/database/backup", **auth_headers(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["last_backup_file"]
        assert len(body["backups"]) == 1
        assert (tmp_path / body["last_backup_file"]).exists()

    def test_restore_endpoint_rejects_bad_file(self, client, admin_user, auth_headers, tmp_path):
        _write_settings(backup_location=str(tmp_path))
        resp = client.post(
            "/api/v1/admin/database/restore",
            {"file": "nope.sqlite3"},
            content_type="application/json",
            **auth_headers(admin_user),
        )
        assert resp.status_code == 400

    # NOTE: the file-DB restore round trip (endpoint + management command) is
    # covered in ``tests/test_db_backup_restore.py``.

    def test_app_settings_round_trip_backup_fields(self, client, admin_user, auth_headers):
        payload = {
            "points_per_analysis": 10,
            "analyses_per_course": 3,
            "active_course_id": None,
            "backup_enabled": True,
            "backup_interval_minutes": 5,
            "backup_location": "my-backups",
            "backup_keep": 3,
        }
        resp = client.put(
            "/api/v1/admin/app-settings", payload, content_type="application/json", **auth_headers(admin_user)
        )
        assert resp.status_code == 200
        s = AppSettings.get_instance()
        assert s.backup_enabled is True
        assert s.backup_interval_minutes == 5
        assert s.backup_location == "my-backups"
        assert s.backup_keep == 3
        # GET reflects it
        got = client.get("/api/v1/admin/app-settings", **auth_headers(admin_user)).json()
        assert got["backup_location"] == "my-backups"

    def test_app_settings_clamps_interval(self, client, admin_user, auth_headers):
        payload = {
            "points_per_analysis": 10,
            "analyses_per_course": 3,
            "active_course_id": None,
            "backup_enabled": True,
            "backup_interval_minutes": 0,
            "backup_location": "backups",
            "backup_keep": 0,
        }
        client.put("/api/v1/admin/app-settings", payload, content_type="application/json", **auth_headers(admin_user))
        s = AppSettings.get_instance()
        assert s.backup_interval_minutes == 1
        assert s.backup_keep == 1


class TestManagementCommands:
    def test_backup_command(self, tmp_path, settings):
        from django.core.management import call_command

        _write_settings(backup_location=str(tmp_path))
        from io import StringIO

        out = StringIO()
        call_command("backup_database", stdout=out)
        assert "Backup written to" in out.getvalue()
        assert any(tmp_path.glob("flamecheck-*.sqlite3"))

    # NOTE: the restore management command is covered in
    # ``tests/test_db_backup_restore.py`` (it needs a file DB).
