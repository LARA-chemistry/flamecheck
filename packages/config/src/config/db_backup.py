"""
SQLite database backup/restore service (admin).

Backups are consistent snapshots taken with SQLite's online backup API
(``sqlite3.Connection.backup``), which is safe to run against a live database
even while other requests hold open transactions. Restores swap the database
file atomically (``os.replace``) and close all pooled connections so
subsequent requests open the restored file.

Only the SQLite backend is supported (the project's default); other engines
raise :class:`BackupNotSupported` with an actionable message.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import OperationalError, connections
from django.utils import timezone

from config.models import AppSettings

logger = logging.getLogger("flamecheck.backup")

#: Prefix of generated backup files (also used for pruning).
BACKUP_FILE_PREFIX = "flamecheck-"
BACKUP_FILE_SUFFIX = ".sqlite3"

#: How often the in-process scheduler wakes up to check for a due backup.
SCHEDULER_POLL_SECONDS = 30

_FILENAME_RE = re.compile(
    rf"^{re.escape(BACKUP_FILE_PREFIX)}\d{{8}}-\d{{6}}(-\d{{6}})?{re.escape(BACKUP_FILE_SUFFIX)}$"
)


class BackupError(Exception):
    """A backup/restore operation failed (user-presentable message)."""


class BackupNotSupported(BackupError):
    """The configured database backend does not support the backup feature."""


def _connection() -> object:
    """Return the default database connection."""
    return connections["default"]


def _reset_single_connection(wrapper: object) -> None:
    """
    Close one Django connection wrapper and reset it to reconnect fresh.

    Calling ``wrapper.close()`` inside an atomic block (``ATOMIC_REQUESTS``)
    closes the raw handle but leaves ``wrapper.connection`` set and flags
    ``closed_in_transaction``, so a later ``close()`` early-returns and the
    wrapper keeps handing out the closed handle. Clearing the reference and
    flags here makes the next query reopen a fresh connection to (the
    restored) file.
    """
    wrapper.close()
    wrapper.connection = None
    wrapper.closed_in_transaction = False
    wrapper.needs_rollback = False


def _require_sqlite() -> None:
    conn = _connection()
    if conn.vendor != "sqlite":
        raise BackupNotSupported(
            f"Database backups are supported for the SQLite backend, but this deployment uses "
            f"'{conn.vendor}'. For other engines, use the native tooling (e.g. pg_dump for Postgres)."
        )


def _is_memory_name(name: str) -> bool:
    """True for in-memory SQLite names (``:memory:`` and ``file:...mode=memory`` URIs)."""
    if not name or name == ":memory:":
        return True
    if name.startswith("file:"):
        from urllib.parse import parse_qs, urlsplit

        parts = urlsplit(name)
        query = parse_qs(parts.query)
        if "memory" in query.get("mode", []):
            return True
    return False


def _raw_db_name() -> str:
    """The raw SQLite database name as configured (file path or memory URI)."""
    return str(_connection().settings_dict.get("NAME") or "")


def _db_path() -> Path | None:
    """Absolute path of the SQLite database file, or None for in-memory databases."""
    name = _raw_db_name()
    if _is_memory_name(name):
        return None
    # A ``file:`` URI may carry query options; back up the referenced file.
    if name.startswith("file:"):
        from urllib.parse import urlsplit

        name = urlsplit(name).path
    return Path(name).resolve()


def resolve_backup_location(location: str | None) -> Path:
    """Resolve the configured backup directory (relative paths against the project root)."""
    raw = (location or "").strip() or "backups"
    path = Path(raw)
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    return path


def _list_backup_files(location: Path) -> list[dict]:
    """All ``*.sqlite3`` files in ``location`` as dicts (newest first)."""
    if not location.is_dir():
        return []
    entries = []
    for p in location.glob(f"*{BACKUP_FILE_SUFFIX}"):
        if not p.is_file():
            continue
        stat = p.stat()
        entries.append(
            {
                "file": p.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo("UTC")).isoformat(),
                "managed": bool(_FILENAME_RE.match(p.name)),
            }
        )
    entries.sort(key=lambda e: e["modified_at"], reverse=True)
    return entries[:50]


def run_backup(location: Path, keep: int | None = None) -> dict:
    """
    Take one consistent backup of the live database into ``location``.

    The snapshot is written as ``flamecheck-YYYYMMDD-HHMMSS.sqlite3`` using
    SQLite's online backup API. The source is opened as a fresh, independent
    connection to the database file (not Django's pooled connection, which may
    hold an open transaction), so the backup never blocks on live requests and
    captures the last committed state. The result is integrity-checked and old
    managed backups are pruned to ``keep``.

    Args:
        location: Directory to write the backup into (created if missing).
        keep: Number of managed backups to keep (default from AppSettings).

    Returns:
        dict: ``{"file", "path", "size"}`` of the new backup.

    Raises:
        BackupNotSupported: If the database backend is not SQLite.
        BackupError: If the snapshot could not be written or verified.

    """
    _require_sqlite()
    if keep is None:
        keep = AppSettings.get_instance().backup_keep
    location.mkdir(parents=True, exist_ok=True)
    # Microseconds keep rapid successive backups from colliding on one file.
    target = location / f"{BACKUP_FILE_PREFIX}{timezone.now():%Y%m%d-%H%M%S-%f}{BACKUP_FILE_SUFFIX}"

    db_path = _db_path()
    if db_path is None:
        # In-memory database (e.g. the test suite): the data only lives on the
        # live pooled connection. Both the backup API and VACUUM INTO refuse
        # to run from inside an open transaction, so rebuild the snapshot
        # from a SQL dump of the committed schema and rows. The dump does not
        # emit DROP statements, so the target must not already exist.
        raw = _connection().connection
        if raw is None:
            raise BackupError("The in-memory database has no open connection to snapshot.")
        if target.exists():
            target.unlink()
        destination = sqlite3.connect(str(target))
        try:
            for line in raw.iterdump():
                destination.execute(line)  # the dump emits its own BEGIN/COMMIT
        except sqlite3.Error as exc:
            destination.close()
            target.unlink(missing_ok=True)
            raise BackupError(f"Backup failed: {exc}") from exc
        destination.close()
    else:
        # File database: a fresh, independent connection never blocks on the
        # transactions held by live requests and captures the committed state.
        source = sqlite3.connect(str(db_path))
        destination = sqlite3.connect(str(target))
        try:
            source.backup(destination)
        except sqlite3.Error as exc:
            destination.close()
            source.close()
            target.unlink(missing_ok=True)
            raise BackupError(f"Backup failed: {exc}") from exc
        finally:
            destination.close()
            source.close()

    verify = sqlite3.connect(str(target))
    try:
        ok = verify.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        verify.close()
    if ok != "ok":
        target.unlink(missing_ok=True)
        raise BackupError(f"Backup integrity check failed for {target.name} ({ok}).")

    _prune(location, keep)
    size = target.stat().st_size
    logger.info("Database backup written to %s (%d bytes)", target, size)
    return {"file": target.name, "path": str(target), "size": size}


def _prune(location: Path, keep: int) -> None:
    """Delete managed backups beyond the newest ``keep`` (unmanaged files are kept)."""
    managed = sorted(
        (p for p in location.glob(f"{BACKUP_FILE_PREFIX}*{BACKUP_FILE_SUFFIX}") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in managed[keep:]:
        old.unlink(missing_ok=True)
        logger.info("Pruned old backup %s", old.name)


def _swap_file_database(conn: object, db_path: Path, source: Path) -> None:
    """
    Atomically replace a file-based database with ``source``.

    The backup is copied through the online backup API into a temp file
    (normalising WAL state) and integrity-checked, then ``os.replace`` swaps
    it over the live file (atomic on the same filesystem). WAL sidecar files
    of the old database are dropped, and the pooled connections are reset so
    subsequent requests open the restored file.

    Args:
        conn: The default Django connection (used to release its handle).
        db_path: The live database file to replace.
        source: The verified backup file to copy in.

    """
    tmp = db_path.with_name(f".{db_path.name}.restore-tmp")
    target_conn = sqlite3.connect(str(tmp))
    try:
        source_conn = sqlite3.connect(str(source))
        try:
            source_conn.backup(target_conn)
        finally:
            source_conn.close()
        ok = target_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise BackupError("Restored file failed its integrity check; restore aborted.")
    except sqlite3.Error as exc:
        target_conn.close()
        tmp.unlink(missing_ok=True)
        raise BackupError(f"Copying the backup failed: {exc}") from exc
    target_conn.close()

    # Release the pooled handles (a single close per connection, not
    # close_all, so an enclosing test transaction stays intact), then swap.
    for alias in connections:
        if connections[alias] is conn:
            _reset_single_connection(connections[alias])
    try:
        os.replace(tmp, db_path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise BackupError(f"Swapping the database file failed: {exc}") from exc
    for suffix in ("-wal", "-shm"):
        (db_path.parent / (db_path.name + suffix)).unlink(missing_ok=True)


def _relocate_to_file(conn: object, source: Path, target: Path) -> None:
    """
    Relocate an in-memory database connection to ``target`` (a copy of ``source``).

    A shared-cache in-memory database is locked to its single connection, so
    its contents cannot be swapped in place. Instead the backup is copied into
    a real file (normalising WAL state) and the connection is pointed at that
    file. ``source`` is only read (via the backup API), so the live
    connection's open transaction is never disturbed.

    Args:
        conn: The default Django database connection.
        source: The verified backup file to copy from.
        target: The destination file the connection will be relocated to.

    """
    target_conn = sqlite3.connect(str(target))
    try:
        source_conn = sqlite3.connect(str(source))
        try:
            source_conn.backup(target_conn)
        finally:
            source_conn.close()
        ok = target_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise BackupError("Restored file failed its integrity check; restore aborted.")
    except sqlite3.Error as exc:
        target_conn.close()
        target.unlink(missing_ok=True)
        raise BackupError(f"Copying the backup failed: {exc}") from exc
    target_conn.close()

    conn.close()  # release the handle to the (locked) in-memory database
    conn.settings_dict["NAME"] = str(target)


def restore_backup(location: Path, filename: str) -> dict:
    """
    Restore the database from a backup file in ``location``.

    The backup is integrity-checked, then applied:

    * **File-based database** — the live database file is atomically replaced
      (``os.replace``) and pooled connections are closed, so ``DATABASE_URL``
      stays valid across a restart.
    * **In-memory database** (e.g. the test suite) — there is no file to
      swap, so the connection is relocated to a real file holding the
      restored data (a restart would fall back to an empty in-memory DB).

    A restart is recommended after restoring a file database for full certainty.

    Args:
        location: Directory containing the backup files.
        filename: File name of the backup (must be inside ``location``).

    Returns:
        dict: ``{"file", "path", "size"}`` of the backup used.

    Raises:
        BackupNotSupported: If the database backend is not SQLite.
        BackupError: If the file is missing/invalid or the restore failed.

    """
    _require_sqlite()
    conn = _connection()
    db_path = _db_path()

    # Reject path traversal: only bare file names from the backup directory.
    name = os.path.basename(filename.strip())
    source = (location / name).resolve()
    if source.parent != location.resolve() or not source.is_file() or not source.name.endswith(BACKUP_FILE_SUFFIX):
        raise BackupError(f"Backup file {filename!r} not found in the backup location.")

    check = sqlite3.connect(str(source))
    try:
        ok = check.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise BackupError(f"Backup {name} failed its integrity check ({ok}); restore aborted.")
    except sqlite3.Error as exc:
        check.close()
        raise BackupError(f"Backup {name} could not be read: {exc}") from exc
    check.close()

    if db_path is not None:
        _swap_file_database(conn, db_path, source)
        final_path = db_path
    else:
        # In-memory database: there is no file to swap, so relocate the
        # connection to a real file holding the restored data.
        relocated = location / f".restored-{name}"
        _relocate_to_file(conn, source, relocated)
        final_path = relocated

    size = final_path.stat().st_size
    logger.info("Database restored from %s", name)
    return {"file": name, "path": str(final_path), "size": size}


def run_if_due() -> dict | None:
    """
    Run a backup if the scheduled backup is enabled and due (scheduler entry point).

    Reads the AppSettings singleton; if ``backup_enabled`` is set and the last
    backup is older than ``backup_interval_minutes`` (or never ran), takes a
    backup and records the result. Safe to call from multiple processes: at
    worst a couple of processes back up concurrently (extra files, pruned
    later), never a corrupt state.

    Returns:
        dict | None: The new backup summary, or None when nothing was due.

    """
    try:
        s = AppSettings.get_instance()
    except OperationalError as exc:
        # The schema is out of date (e.g. a stale SQLite volume whose
        # config_appsettings table predates the backup_* columns, so
        # `migrate` finds nothing to apply). This is not a backup failure;
        # report it once as a warning rather than spammed every poll.
        logger.warning(
            "Scheduled backup skipped: AppSettings schema is out of date (%s). "
            "Run `manage.py migrate` (recreate the database volume if needed).",
            exc,
        )
        return None
    if not s.backup_enabled:
        return None
    interval = timedelta(minutes=max(1, s.backup_interval_minutes))
    if s.last_backup_at is not None and (timezone.now() - s.last_backup_at) < interval:
        return None
    try:
        result = run_backup(resolve_backup_location(s.backup_location), s.backup_keep)
    except BackupNotSupported:
        return None  # non-SQLite deployment: stay quiet (the API reports it)
    s = AppSettings.get_instance()
    s.last_backup_at = timezone.now()
    s.last_backup_file = result["file"]
    s.save(update_fields=["last_backup_at", "last_backup_file"])
    return result


def get_status() -> dict:
    """
    Collect the database section status for the admin API.

    Returns:
        dict: Backend info, current backup settings, last backup/restore info,
        and the list of backup files in the configured location.

    """
    s = AppSettings.get_instance()
    conn = _connection()
    vendor = conn.vendor
    location = resolve_backup_location(s.backup_location)
    backups = _list_backup_files(location) if vendor == "sqlite" else []
    return {
        "backend": vendor,
        "sqlite": vendor == "sqlite",
        "database_file": str(_db_path()) if vendor == "sqlite" else None,
        "enabled": bool(s.backup_enabled),
        "interval_minutes": int(s.backup_interval_minutes),
        "location": (s.backup_location or "").strip() or "backups",
        "keep": int(s.backup_keep),
        "last_backup_at": s.last_backup_at.isoformat() if s.last_backup_at else None,
        "last_backup_file": s.last_backup_file or None,
        "last_restore_at": s.last_restore_at.isoformat() if s.last_restore_at else None,
        "last_restore_file": s.last_restore_file or None,
        "backups": backups,
    }


def mark_restored(filename: str) -> None:
    """Record a successful restore on the AppSettings singleton."""
    s = AppSettings.get_instance()
    s.last_restore_at = timezone.now()
    s.last_restore_file = filename
    s.save(update_fields=["last_restore_at", "last_restore_file"])
