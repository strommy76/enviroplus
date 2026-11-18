"""Actual local-rclone objects qualify retention and source isolation."""

import hashlib
import json
import socket
from pathlib import Path

import pytest

from backup_snapshots import prune_database_snapshots, snapshot_retention_plan


def _delivery(manifests, name, remote_dir, payload):
    manifests.mkdir(exist_ok=True)
    digest = hashlib.md5(payload).hexdigest()
    (manifests / f"backup_{name}.json").write_text(
        json.dumps(
            {
                "generated_utc": "2026-11-18T00:00:00Z",
                "results": [
                    {
                        "kind": "file",
                        "source": str(manifests.parent / name),
                        "remote_object": str(remote_dir / name),
                        "verified": True,
                        "local_hash": digest,
                        "remote_hash": digest,
                    }
                ],
            }
        )
    )


def test_retention_keeps_two_proven_copies_and_only_prunes_older_producer_objects(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    manifests = tmp_path / "manifests"
    old = "enviro_20260101T000000Z.db"  # its old manifest has already aged out
    second = "enviro_20260102T000000Z.db"
    third = "enviro_20260103T000000Z.db"
    newer = "enviro_20260104T000000Z.db"  # unverified, must not be deleted
    sibling = "enviro_1min_20250101T000000Z.db"
    for name in [old, second, third, newer, sibling, "operator.db"]:
        (remote / name).write_bytes(name.encode())
    for name in [second, third]:
        _delivery(manifests, name, remote, name.encode())
    before = {p.name: p.read_bytes() for p in manifests.iterdir()}
    plan = snapshot_retention_plan(str(remote), "enviro", 2, manifests, config_path=None)
    assert plan == {"retained": [second, third], "delete": [old]}
    assert (remote / old).exists(), "the planning interface mutated the remote"
    prune_database_snapshots(str(remote), "enviro", 2, manifests, config_path=None)
    assert {p.name for p in remote.iterdir()} == {second, third, newer, sibling, "operator.db"}
    assert {p.name: p.read_bytes() for p in manifests.iterdir()} == before


def test_changed_remote_bytes_do_not_qualify_as_a_second_verified_copy(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    manifests = tmp_path / "manifests"
    old, first, second = [f"enviro_2026010{n}T000000Z.db" for n in [1, 2, 3]]
    for name in [old, first, second]:
        (remote / name).write_bytes(name.encode())
    for name in [first, second]:
        _delivery(manifests, name, remote, name.encode())
    (remote / first).write_bytes(b"corrupted after delivery")
    result = prune_database_snapshots(str(remote), "enviro", 2, manifests, config_path=None)
    assert result == {"retained": [second], "delete": []}
    assert {p.name for p in remote.iterdir()} == {old, first, second}


def test_committed_units_follow_native_host_configuration():
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / "config/backup.json").read_text())["hosts"][socket.gethostname()]
    timer = (root / "enviro_backup.timer").read_text().splitlines()
    service = (root / "enviro_backup.service").read_text().splitlines()
    assert f"OnCalendar={cfg['cadence']['on_calendar']}" in timer
    assert f"RandomizedDelaySec={cfg['cadence']['randomized_delay_seconds']}" in timer
    assert f"TimeoutStartSec={cfg['cadence']['execution_timeout_seconds']}" in service
    assert cfg["local"] is None


@pytest.mark.parametrize("absent", ["host", "drive", "local", "cadence", "coverage_command"])
def test_required_configuration_absence_is_loud(tmp_path, absent):
    from scripts.backup_enviro import BackupError, load_config

    document = json.loads((Path(__file__).resolve().parents[1] / "config/backup.json").read_text())
    if absent == "host":
        document["hosts"].pop(socket.gethostname())
    else:
        document["hosts"][socket.gethostname()].pop(absent)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(document))
    with pytest.raises(BackupError):
        load_config(path)
