"""Real SQLite snapshots and native shared-service integration."""

import json
import os
import socket
import sqlite3
import sys
from pathlib import Path

import pytest
from shared.backup_service import run
from shared.backup_status import latest_status
from shared.duplicacy_cli import Duplicacy

from sqlite_backup import capture, verify


def database(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE readings (value TEXT)")
    connection.execute("CREATE TABLE empty_but_valid (value TEXT)")
    connection.execute("INSERT INTO readings VALUES ('captured')")
    connection.commit()
    return connection


def test_wal_capture_is_committed_and_restore_uses_pinned_evidence(tmp_path):
    source = tmp_path / "live.db"
    connection = database(source)
    connection.execute("INSERT INTO readings VALUES ('uncommitted')")
    output = tmp_path / "payload"
    output.mkdir()
    evidence = capture(source, output)
    assert evidence["facts"]["table_rows"] == {"empty_but_valid": 0, "readings": 1}
    with sqlite3.connect(output / "snapshot.db") as snapshot:
        assert snapshot.execute("SELECT value FROM readings").fetchall() == [("captured",)]
    connection.commit()
    connection.execute("DELETE FROM readings")
    connection.commit()
    connection.close()
    assert verify(output) == evidence


def test_same_cardinality_restored_corruption_fails(tmp_path):
    source = tmp_path / "live.db"
    database(source).close()
    output = tmp_path / "payload"
    output.mkdir()
    capture(source, output)
    with sqlite3.connect(output / "snapshot.db") as restored:
        restored.execute("UPDATE readings SET value='tampered'")
    with pytest.raises(RuntimeError, match="captured evidence"):
        verify(output)


def test_enviro_runs_real_producers_through_common_service(tmp_path):
    binary = os.environ.get("DUPLICACY_TEST_BINARY")
    if binary is None:
        pytest.skip("Native consumer qualification requires DUPLICACY_TEST_BINARY")
    source = tmp_path / "live.db"
    database(source).close()
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "capture.ndjson").write_bytes(b'{"original":true}\n')
    storage = tmp_path / "storage"
    storage.mkdir()
    config = tmp_path / "config/backup.json"
    config.parent.mkdir()
    host = {
        "environment_file": None,
        "state_dir": str(tmp_path / "state"),
        "duplicacy_binary": binary,
        "metadata_timeout_seconds": 300,
        "components": {
            "database": {
                "authority": "authoritative",
                "source_path": str(source),
                "capture_argv": [
                    sys.executable,
                    "-m",
                    "sqlite_backup",
                    "capture",
                    "--config",
                    str(config),
                    "--component",
                    "database",
                ],
                "capture_timeout_seconds": 300,
                "estimate_argv": [
                    sys.executable,
                    "-m",
                    "sqlite_backup",
                    "estimate",
                    "--config",
                    str(config),
                    "--component",
                    "database",
                ],
                "estimate": {"capture_evidence_bytes": 379, "native_metadata_bytes_per_file": 1024},
            },
            "raw_capture": {
                "authority": "authoritative",
                "source_path": str(raw),
                "capture_argv": None,
                "estimate_argv": [
                    sys.executable,
                    "-m",
                    "shared.backup_estimates",
                    "--config",
                    str(config),
                    "--component",
                    "raw_capture",
                ],
                "estimate": {"native_metadata_bytes_per_file": 163},
            },
        },
        "destinations": {
            "local": {
                "storage": str(storage),
                "copies": 2,
                "execution_timeout_seconds": 300,
                "capacity_argv": [
                    sys.executable,
                    "-m",
                    "shared.backup_capacity",
                    "local",
                    str(storage),
                ],
            },
            "drive": None,
        },
    }
    config.write_text(json.dumps({"project": "enviroplus", "hosts": {socket.gethostname(): host}}))
    first = run(config)
    assert first["ok"]
    assert latest_status(config)["ok"]
    restore = tmp_path / "restore"
    restore.mkdir()
    recovery = Duplicacy(
        binary, tmp_path / "restore-control", restore, str(storage), "database", 300
    )
    recovery.initialize()
    recovery.command("restore", "-r", str(first["deliveries"][0]["revision"]))
    assert verify(restore)["facts"]["table_rows"] == {"empty_but_valid": 0, "readings": 1}
    source.rename(tmp_path / "temporarily-offline.db")
    result = run(config)
    assert not result["ok"]
    assert [delivery["component"] for delivery in result["deliveries"]] == ["raw_capture"]
    assert not latest_status(config)["ok"]
    assert (raw / "capture.ndjson").read_bytes() == b'{"original":true}\n'


def test_native_unit_uses_common_owner_and_project_cadence():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/backup.json").read_text())["hosts"][socket.gethostname()]
    service = (root / "enviro_backup.service").read_text()
    timer = (root / "enviro_backup.timer").read_text()
    assert "-m shared.backup_service --config " in service
    assert "OnFailure=stocks_ops_alert@%n.service" in service
    assert f"TimeoutStartSec={config['cadence']['execution_timeout_seconds']}" in service
    assert f"OnCalendar={config['cadence']['on_calendar']}" in timer
