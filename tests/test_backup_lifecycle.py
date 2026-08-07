"""
--------------------------------------------------------------------------------
FILE:        test_backup_lifecycle.py
PATH:        ~/projects/enviroplus/tests/test_backup_lifecycle.py
DESCRIPTION: Staging lifecycle of the backup lane: what a run leaves behind on
             success, on failure, and on a dry run.

             Delete-on-success plus keep-on-failure is exactly the control flow
             a later edit regresses silently -- it has no visible symptom until
             the SD card fills or the artifact you need to diagnose a failure
             has already been removed. Both directions are asserted here.

             Replication itself is stubbed. The transport is proven in
             shared/tests/test_offsite_replication.py against a real rclone;
             what is under test here is which local files survive a run.

CHANGELOG:
2026-08-07 06:58      Claude     [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/pistrommy/projects")

_SCRIPT = Path("/home/pistrommy/projects/enviroplus/scripts/backup_enviro.py")
_spec = importlib.util.spec_from_file_location("backup_enviro", _SCRIPT)
backup_enviro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backup_enviro)

from shared.offsite_replication import ReplicationError, ReplicationResult  # noqa: E402


def _result(kind, source, remote_object):
    return ReplicationResult(
        kind=kind, source=str(source), remote_object=remote_object,
        bytes_transferred=1, local_hash=None, remote_hash=None, verified=True,
        started_utc="2026-08-07T00:00:00+00:00",
        finished_utc="2026-08-07T00:00:01+00:00",
    )


@pytest.fixture()
def lane(tmp_path):
    """A complete backup lane rooted in tmp_path."""
    db = tmp_path / "enviro.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE readings (ts TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO readings VALUES ('2026-08-07T00:00:00Z')")
    conn.commit()
    conn.close()

    raw = tmp_path / "raw-capture" / "ambient"
    raw.mkdir(parents=True)
    (raw / "2026-08-07.ndjson").write_text('{"n":1}\n')

    staging = tmp_path / ".backup-staging"
    cfg = {
        "remote": {"rclone_remote_name": "test", "rclone_remote_path": "backups/x"},
        "sources": {
            "database": {"kind": "sqlite_snapshot", "source_path": str(db),
                         "remote_subpath": "database"},
            "raw_capture": {"kind": "tree",
                            "source_path": str(tmp_path / "raw-capture"),
                            "remote_subpath": "raw-capture"},
        },
        "local_staging": {"staging_dir": str(staging), "dir_mode": "0700",
                          "file_mode": "0600", "failed_run_retention": 1},
        "manifest": {"manifest_dir": str(staging / "manifests"),
                     "retention_count": 30},
    }
    path = tmp_path / "backup.json"
    path.write_text(json.dumps(cfg))
    return path, staging, tmp_path


def _stub_success(monkeypatch):
    monkeypatch.setattr(backup_enviro, "replicate_file",
                        lambda src, obj, **kw: _result("file", src, obj))
    monkeypatch.setattr(backup_enviro, "replicate_tree",
                        lambda src, obj, **kw: _result("tree", src, obj))


def _snapshots(staging: Path) -> list[str]:
    return sorted(p.name for p in staging.glob("enviro_*.db"))


# ── Gate: the success path leaves no staged snapshot ─────────────────────────

def test_verified_upload_leaves_no_staged_snapshot(lane, monkeypatch):
    """Mutation: restore the prune to the failure path."""
    config, staging, _ = lane
    _stub_success(monkeypatch)

    assert backup_enviro.run(config) == 0
    assert _snapshots(staging) == [], "a verified run left its staged snapshot behind"


def test_success_also_clears_a_snapshot_left_by_an_earlier_failure(lane, monkeypatch):
    """The defect: removing only the current run's file.

    A snapshot kept to explain a failed run has no purpose once a later run
    succeeds. Clearing only the current file left every failed run's artifact on
    disk for good.
    """
    config, staging, _ = lane
    staging.mkdir(parents=True, exist_ok=True)
    orphan = staging / "enviro_20260101T000000Z.db"
    orphan.write_bytes(b"left by a failed run")

    _stub_success(monkeypatch)
    assert backup_enviro.run(config) == 0

    assert not orphan.exists(), \
        "a snapshot from an earlier failed run survived a successful run"
    assert _snapshots(staging) == []


# ── Gate: a failed run keeps exactly one snapshot for diagnosis ──────────────

def test_failed_upload_keeps_its_snapshot(lane, monkeypatch):
    """The opposite direction, and just as easy to regress."""
    config, staging, _ = lane

    def boom(src, obj, **kw):
        raise ReplicationError("remote refused")

    monkeypatch.setattr(backup_enviro, "replicate_file", boom)

    with pytest.raises(ReplicationError):
        backup_enviro.run(config)

    assert len(_snapshots(staging)) == 1, \
        "a failed run did not keep the artifact needed to diagnose it"


def test_repeated_failures_do_not_accumulate_snapshots(lane, monkeypatch):
    """failed_run_retention bounds the disk cost of a persistently dead remote.

    Seeded with distinct prior snapshots rather than by looping the run: the
    staged filename is stamped to the second, so repeated runs inside one second
    collide on the same name and a test that loops would measure that collision
    instead of the bound -- it stays green against a lane with no bound at all.
    """
    config, staging, _ = lane
    staging.mkdir(parents=True, exist_ok=True)
    for day in ("20260101", "20260102", "20260103"):
        (staging / f"enviro_{day}T000000Z.db").write_bytes(b"prior failed run")

    def boom(src, obj, **kw):
        raise ReplicationError("remote refused")

    monkeypatch.setattr(backup_enviro, "replicate_file", boom)
    with pytest.raises(ReplicationError):
        backup_enviro.run(config)

    kept = _snapshots(staging)
    assert len(kept) == 1, \
        f"failed runs accumulated snapshots without bound: {kept}"
    assert kept[0].startswith("enviro_2026"), kept
    assert not kept[0].startswith("enviro_20260101"), \
        "the retained snapshot should be this run's, not the oldest"


# ── Gate: a dry run changes nothing ──────────────────────────────────────────

def test_dry_run_creates_no_snapshot(lane, monkeypatch):
    """Mutation: create the snapshot before the branch.

    The snapshot was built and only then was the dry-run branch taken, so a dry
    run wrote a full copy of the database into staging and nothing ever removed
    it.
    """
    config, staging, _ = lane
    _stub_success(monkeypatch)

    assert backup_enviro.run(config, dry_run=True) == 0
    assert _snapshots(staging) == [], "a dry run created a snapshot"


def test_dry_run_does_not_create_the_staging_directory(lane, monkeypatch):
    """"Leaves staging unchanged" includes not bringing it into existence."""
    config, staging, _ = lane
    assert not staging.exists(), "fixture already created staging"
    _stub_success(monkeypatch)

    backup_enviro.run(config, dry_run=True)

    assert not staging.exists(), "a dry run created the staging directory"


@pytest.mark.parametrize("bad", ["2", 2.5, -1, True, None])
def test_a_non_integer_failed_run_retention_fails_at_load(lane, bad):
    """Presence alone left the trap one step along.

    A string value passes load and every successful run, then raises a bare
    TypeError inside the failure handler -- the same latent shape the presence
    check exists to remove, moved rather than removed. True is rejected
    explicitly because bool subclasses int and would silently mean 1.
    """
    config, _, _ = lane
    cfg = json.loads(config.read_text())
    cfg["local_staging"]["failed_run_retention"] = bad
    config.write_text(json.dumps(cfg))

    with pytest.raises(backup_enviro.BackupError, match="failed_run_retention"):
        backup_enviro.load_config(config)


def test_a_config_without_failed_run_retention_fails_at_load(lane):
    """Not on the first failure, which is when the message matters most.

    Matched on the WORDING, deliberately. The type check below backstops a
    missing key too (None is not an int), so a test that only asserted "some
    BackupError" stayed green with the presence check deleted -- it was grading
    the backstop. The presence branch earns its place by naming the likeliest
    misconfiguration, an older config, so that is what the gate holds it to.
    """
    config, _, _ = lane
    cfg = json.loads(config.read_text())
    del cfg["local_staging"]["failed_run_retention"]
    config.write_text(json.dumps(cfg))

    with pytest.raises(backup_enviro.BackupError, match="missing failed_run_retention"):
        backup_enviro.load_config(config)


def test_dry_run_writes_no_manifest(lane, monkeypatch):
    config, staging, _ = lane
    _stub_success(monkeypatch)

    backup_enviro.run(config, dry_run=True)

    manifests = list((staging / "manifests").glob("backup_*.json")) \
        if (staging / "manifests").exists() else []
    assert manifests == [], "a dry run wrote a manifest"


def test_dry_run_leaves_the_source_tree_untouched(lane, monkeypatch):
    """The raw tier is canonical; a backup must never write into it."""
    config, _, root = lane
    raw = root / "raw-capture"
    before = {p.relative_to(raw).as_posix(): p.stat().st_size for p in raw.rglob("*")}

    _stub_success(monkeypatch)
    backup_enviro.run(config, dry_run=True)

    after = {p.relative_to(raw).as_posix(): p.stat().st_size for p in raw.rglob("*")}
    assert before == after


def test_retention_larger_than_the_backlog_deletes_nothing(lane, monkeypatch):
    """The slice index must not go negative.

    `older[:len(older) - keep_older]` wraps when keep_older exceeds the backlog:
    with two prior snapshots and keep_older=3 it deletes the oldest instead of
    keeping both. The wrap zone is len(older) < keep_older < 2*len(older) --
    past 2x Python clamps the slice to empty and the defect becomes invisible,
    which is why an extreme mutation could not find it.
    """
    config, staging, _ = lane
    cfg = json.loads(config.read_text())
    cfg["local_staging"]["failed_run_retention"] = 4      # keep_older = 3
    config.write_text(json.dumps(cfg))

    staging.mkdir(parents=True, exist_ok=True)
    priors = ["enviro_20260101T000000Z.db", "enviro_20260102T000000Z.db"]
    for name in priors:                                   # 2 older < 3 kept < 4
        (staging / name).write_bytes(b"prior failed run")

    def boom(src, obj, **kw):
        raise ReplicationError("remote refused")

    monkeypatch.setattr(backup_enviro, "replicate_file", boom)
    with pytest.raises(ReplicationError):
        backup_enviro.run(config)

    survivors = _snapshots(staging)
    for name in priors:
        assert name in survivors, \
            f"{name} was deleted although retention asked to keep more than exist"


def test_success_does_not_remove_a_concurrent_runs_newer_snapshot(lane, monkeypatch):
    """Clearing by pattern alone removes a file another run is still using.

    Reachable by a manual start while the timer's run is in flight -- which is
    exactly how this lane gets exercised by hand.
    """
    config, staging, _ = lane
    staging.mkdir(parents=True, exist_ok=True)
    concurrent = staging / "enviro_29991231T235959Z.db"      # a later stamp
    concurrent.write_bytes(b"another run is still uploading this")

    _stub_success(monkeypatch)
    assert backup_enviro.run(config) == 0

    assert concurrent.exists(), \
        "the success path deleted a concurrently-running backup's snapshot"


def test_success_does_not_remove_a_different_sources_snapshots(lane, monkeypatch):
    """A glob on `<stem>_*` also matches a source whose stem starts with it.

    Name-derived selection is the failure the replication guard exists to
    remove; it must not reappear in the cleanup.
    """
    config, staging, _ = lane
    staging.mkdir(parents=True, exist_ok=True)
    # The sibling stem must sort BELOW this run's ceiling, or the ceiling bound
    # protects it on its own and the test never exercises stem matching at all.
    # 'enviro_1min' does; 'enviro_secondary' does not, because 's' > '2'.
    other = staging / "enviro_1min_20260101T000000Z.db"
    other.write_bytes(b"a different source's snapshot")
    assert other.name < "enviro_2", "the fixture no longer sorts below the ceiling"

    _stub_success(monkeypatch)
    assert backup_enviro.run(config) == 0

    assert other.exists(), \
        "cleanup matched a different source by stem prefix and deleted its snapshot"


def test_a_verified_run_leaves_the_source_tree_untouched(lane, monkeypatch):
    config, _, root = lane
    raw = root / "raw-capture"
    before = {p.relative_to(raw).as_posix(): p.stat().st_size for p in raw.rglob("*")}

    _stub_success(monkeypatch)
    backup_enviro.run(config)

    after = {p.relative_to(raw).as_posix(): p.stat().st_size for p in raw.rglob("*")}
    assert before == after
