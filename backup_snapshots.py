"""
--------------------------------------------------------------------------------
FILE:        backup_snapshots.py
PATH:        ~/projects/enviroplus/backup_snapshots.py
DESCRIPTION: Native database snapshot objects and evidence-based remote retention.

CHANGELOG:
2026-11-18            Codex      [Feature] Keep configured verified database copies
                                      and prune only older exact producer objects.
--------------------------------------------------------------------------------
"""

import json
import logging
import re
import subprocess
from pathlib import Path

from shared.offsite_replication import ReplicationError, probe_remote_tree

log = logging.getLogger(__name__)


def snapshot_stamp(name: str, stem: str) -> str | None:
    """Recognize this producer's exact object shape, not a stem-prefix glob."""
    match = re.fullmatch(re.escape(stem) + r"_(\d{8}T\d{6}Z)\.db", name)
    return match[1] if match else None


def run_rclone(config_path: str | None, *args: str) -> str:
    """Use native rclone retry/idle limits within the caller's run lifetime."""
    argv = ["rclone"] + (["--config", config_path] if config_path else []) + list(args)
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        raise ReplicationError(f"rclone {args[0]} failed: {result.stderr.strip()[:300]}")
    return result.stdout


def snapshot_retention_plan(
    remote_dir: str, stem: str, keep: int, manifest_dir: Path, *, config_path: str | None
) -> dict:
    """Select only older producer objects after proving the retained copies.

    Delivery manifests are append-only observations. Their hashes are compared
    with a fresh remote listing; naming an object alone never proves delivery.
    The returned plan is also the read-only activation inventory interface.
    """
    delivered = {}
    for path in sorted(manifest_dir.glob("backup_*.json")):
        for row in json.loads(path.read_text())["results"]:
            obj = row["remote_object"]
            directory, _, name = obj.rpartition("/")
            if (
                directory == remote_dir
                and snapshot_stamp(name, stem) is not None
                and row["kind"] == "file"
                and row["verified"] is True
                and row["local_hash"] == row["remote_hash"]
                and row["remote_hash"] is not None
            ):
                delivered[name] = row["remote_hash"]
    remote = probe_remote_tree(remote_dir, config_path=config_path)
    owned = sorted(name for name in remote if snapshot_stamp(name, stem) is not None)
    verified = [
        name
        for name in owned
        if remote[name].md5 is not None and remote[name].md5 == delivered.get(name)
    ]
    retained = verified[-keep:]
    # The first successful upload is nominal: it cannot authorize pruning yet.
    deleted = [name for name in owned if name < retained[0]] if len(retained) == keep else []
    return {"retained": retained, "delete": deleted}


def prune_database_snapshots(
    remote_dir: str, stem: str, keep: int, manifest_dir: Path, *, config_path: str | None
) -> dict:
    plan = snapshot_retention_plan(remote_dir, stem, keep, manifest_dir, config_path=config_path)
    log.info("database retention selection: %s", json.dumps(plan))
    for name in plan["delete"]:
        run_rclone(config_path, "deletefile", f"{remote_dir}/{name}")
        log.info("removed database snapshot: %s/%s", remote_dir, name)
    return plan
