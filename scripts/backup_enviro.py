#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        backup_enviro.py
PATH:        ~/projects/enviroplus/scripts/backup_enviro.py
DESCRIPTION: Backs up the enviroplus data tiers offsite and proves the copy.

             Two sources, two shapes, two verbs -- because they are genuinely
             different, not as a preference. enviro.db is a live WAL database
             with four concurrent writers, so it is snapshotted with VACUUM INTO
             and copied as one object. raw-capture is an append-only tree of
             immutable per-day files, so it syncs and only new days transfer.

             Nothing is reported as backed up until the hash of the object that
             actually landed has been compared. The lane this replaces never
             once succeeded and never said so: it was unscheduled, pointed at a
             remote that did not exist, and truncated its own log each run.

USAGE:       python3 scripts/backup_enviro.py [--config PATH] [--dry-run]

CHANGELOG:
2026-08-06 16:34      Claude     [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/pistrommy/projects")

from shared.offsite_replication import (  # noqa: E402
    ReplicationError,
    replicate_file,
    replicate_tree,
    write_manifest,
)

_BASE = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = _BASE / "config" / "backup.json"

log = logging.getLogger("backup_enviro")


class BackupError(RuntimeError):
    """The backup did not demonstrably succeed."""


def load_config(path: Path) -> dict:
    with path.open() as fh:
        cfg = json.load(fh)
    for key in ("remote", "sources", "local_staging", "manifest"):
        if key not in cfg:
            raise BackupError(f"config missing required section: {key}")
    return cfg


def snapshot_sqlite(source: Path, target: Path) -> Path:
    """Consistent snapshot of a live WAL database.

    VACUUM INTO, not a file copy: the database has four concurrent writers and
    a 4 MB WAL, so copying the main file mid-write yields a torn artifact whose
    hash would then certify the tear.
    """
    if not source.is_file():
        raise BackupError(f"database not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        conn.execute("VACUUM INTO ?", (str(target),))
    finally:
        conn.close()
    if not target.is_file() or target.stat().st_size == 0:
        raise BackupError(f"snapshot produced no artifact: {target}")

    # A snapshot that cannot be opened is not a backup. Prove it here, while
    # there is still a machine to fix it on.
    check = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        status = check.execute("PRAGMA integrity_check").fetchone()[0]
        if status != "ok":
            raise BackupError(f"snapshot failed integrity_check: {status}")
        tables = [r[0] for r in check.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        if not tables:
            raise BackupError("snapshot contains no tables")
    finally:
        check.close()
    log.info("snapshot ok: %s (%d bytes, %d tables)",
             target.name, target.stat().st_size, len(tables))
    return target


def prune(directory: Path, pattern: str, keep: int) -> list[str]:
    files = sorted(directory.glob(pattern), key=lambda p: p.name, reverse=True)
    removed = []
    for stale in files[keep:]:
        stale.unlink()
        removed.append(stale.name)
    return removed


def run(config_path: Path, *, dry_run: bool = False) -> int:
    cfg = load_config(config_path)
    remote = cfg["remote"]
    staging = Path(cfg["local_staging"]["staging_dir"])
    rclone_config = remote.get("rclone_config_path")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{remote['rclone_remote_name']}:{remote['rclone_remote_path'].strip('/')}"

    staging.mkdir(parents=True, exist_ok=True)
    os.chmod(staging, int(cfg["local_staging"]["dir_mode"], 8))

    results = []
    for name, src in cfg["sources"].items():
        kind = src["kind"]
        source_path = Path(src["source_path"])
        remote_dir = f"{base}/{src['remote_subpath'].strip('/')}"

        if kind == "sqlite_snapshot":
            snap = staging / f"{source_path.stem}_{stamp}.db"
            snapshot_sqlite(source_path, snap)
            os.chmod(snap, int(cfg["local_staging"]["file_mode"], 8))
            if dry_run:
                log.info("[dry-run] would replicate %s -> %s/%s", snap, remote_dir, snap.name)
                continue
            results.append(replicate_file(snap, f"{remote_dir}/{snap.name}",
                                          config_path=rclone_config))
            dropped = prune(staging, f"{source_path.stem}_*.db",
                            cfg["local_staging"]["retention_count"])
            if dropped:
                log.info("pruned %d stale local snapshot(s): %s", len(dropped), dropped)

        elif kind == "tree":
            if dry_run:
                log.info("[dry-run] would sync %s -> %s", source_path, remote_dir)
                continue
            results.append(replicate_tree(source_path, remote_dir,
                                          config_path=rclone_config))
        else:
            raise BackupError(f"unknown source kind for {name!r}: {kind}")

    if dry_run:
        log.info("[dry-run] complete; nothing transferred")
        return 0

    if not results:
        raise BackupError("no sources replicated -- refusing to report success")

    manifest_dir = Path(cfg["manifest"]["manifest_dir"])
    manifest = write_manifest(manifest_dir / f"backup_{stamp}.json", results,
                              extra={"remote_base": base, "config": str(config_path)})
    prune(manifest_dir, "backup_*.json", cfg["manifest"]["retention_count"])

    total = sum(r.bytes_transferred or 0 for r in results)
    log.info("backup verified: %d source(s), %.1f MB, manifest=%s",
             len(results), total / 1024 / 1024, manifest.name)
    for r in results:
        log.info("  %-6s %-40s verified=%s", r.kind,
                 r.remote_object.split("/")[-1] or r.remote_object, r.verified)
    return 0


def verify_restore(config_path: Path) -> int:
    """Pull the newest remote snapshot back and prove it opens.

    A backup nobody has restored is an assertion. This downloads the object
    that actually landed -- not the local staging copy, which would prove
    nothing about the remote -- and requires it to pass integrity_check and
    carry the tables the live database has.
    """
    import shutil
    import tempfile

    cfg = load_config(config_path)
    remote = cfg["remote"]
    rclone_config = remote.get("rclone_config_path")
    base = f"{remote['rclone_remote_name']}:{remote['rclone_remote_path'].strip('/')}"
    src = cfg["sources"]["database"]
    remote_dir = f"{base}/{src['remote_subpath'].strip('/')}"

    listing = _run_rclone(rclone_config, "lsjson", remote_dir)
    objects = sorted(json.loads(listing), key=lambda o: o["Name"])
    if not objects:
        raise BackupError(f"no snapshot present at {remote_dir} -- nothing to restore")
    newest = objects[-1]["Name"]

    work = Path(tempfile.mkdtemp(prefix="enviro-restore-"))
    try:
        local = work / newest
        _run_rclone(rclone_config, "copyto", f"{remote_dir}/{newest}", str(local))
        if not local.is_file():
            raise BackupError(f"restore produced no file for {newest}")

        conn = sqlite3.connect(f"file:{local}?mode=ro", uri=True)
        try:
            status = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if status != "ok":
                raise BackupError(f"restored snapshot failed integrity_check: {status}")
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in sorted(tables)}
        finally:
            conn.close()

        live = Path(src["source_path"])
        if live.is_file():
            lc = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
            try:
                live_tables = {r[0] for r in lc.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                lc.close()
            missing = live_tables - tables
            if missing:
                raise BackupError(
                    f"restored snapshot is missing live tables: {sorted(missing)}")

        log.info("RESTORE VERIFIED: %s (%d bytes)", newest, local.stat().st_size)
        for table, count in counts.items():
            log.info("  %-18s %d rows", table, count)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run_rclone(config_path: str | None, *args: str) -> str:
    import subprocess
    argv = ["rclone"] + (["--config", config_path] if config_path else []) + list(args)
    result = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise BackupError(f"rclone {args[0]} failed: {result.stderr.strip()[:300]}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-restore", action="store_true",
                        help="pull the newest remote snapshot back and prove it opens")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )
    try:
        if args.verify_restore:
            return verify_restore(args.config)
        return run(args.config, dry_run=args.dry_run)
    except (BackupError, ReplicationError) as exc:
        # Fail loud and leave no manifest. A silent or partial backup that
        # reports success is the failure this lane exists to end.
        log.error("BACKUP FAILED: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
