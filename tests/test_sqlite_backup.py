"""Real SQLite snapshots and native shared-service integration."""

import json
import os
import socket
import sqlite3
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest
import shared
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


def test_enviro_runs_real_producers_through_common_service(tmp_path, monkeypatch):
    binary = os.environ.get("DUPLICACY_TEST_BINARY")
    if binary is None:
        pytest.skip("Native consumer qualification requires DUPLICACY_TEST_BINARY")
    # Producers run from the synthetic project's cwd, not this checkout.
    # Preserve the actual source owners as absolute child import bindings.
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            [
                str(Path(__file__).resolve().parents[1]),
                str(Path(shared.__file__).absolute().parent.parent),
            ]
        ),
    )
    source = tmp_path / "live.db"
    database(source).close()
    monkeypatch.setenv("SQLITE_PATH", str(source))
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
                "capture_argv": [
                    sys.executable,
                    "-m",
                    "sqlite_backup",
                    "capture",
                ],
                "capture_timeout_seconds": 300,
                "estimate_argv": [
                    sys.executable,
                    "-m",
                    "sqlite_backup",
                    "estimate",
                ],
                "estimate": {
                    "capture_evidence_bytes": 379,
                    "native_overhead_fraction": {"numerator": 0, "denominator": 107970939},
                },
            },
            "raw_capture": {
                "authority": "authoritative",
                "source_path": str(raw),
                "capture_argv": None,
                "estimate_argv": [
                    sys.executable,
                    "-m",
                    "shared.backup_estimates",
                ],
                "estimate": {"native_metadata_bytes_per_file": 163},
            },
            "observations": {
                "authority": "authoritative",
                "source_path": str(tmp_path / "state/observations"),
                "capture_argv": None,
                "estimate_argv": [
                    sys.executable,
                    "-m",
                    "shared.backup_estimates",
                    "--config",
                    str(config),
                    "--component",
                    "observations",
                ],
                "estimate": {"native_metadata_bytes_per_file": 1024},
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
    assert not (tmp_path / "state/payloads/database").exists()
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
    assert [delivery["component"] for delivery in result["deliveries"]] == [
        "raw_capture",
        "observations",
    ]
    assert not latest_status(config)["ok"]
    assert (raw / "capture.ndjson").read_bytes() == b'{"original":true}\n'

    # Fresh-directory recovery starts from the retained observations component,
    # not the live evidence tree or a manufactured verification record.
    evidence_dir = tmp_path / "recovered-observations"
    evidence_dir.mkdir()
    observations = Duplicacy(
        binary, tmp_path / "observations-control", evidence_dir, str(storage), "observations", 300
    )
    observations.initialize()
    observed_revision = next(
        d["revision"] for d in result["deliveries"] if d["component"] == "observations"
    )
    observations.command("restore", "-r", str(observed_revision))
    records = [json.loads(p.read_text()) for p in evidence_dir.glob("*.json")]
    complete = max(
        (r for r in records if r["type"] == "run" and r["complete"]),
        key=lambda r: r["generated_utc"],
    )
    assert complete["run_id"] == first["run_id"]
    for selected in complete["deliveries"]:
        recovered = tmp_path / ("cohort-" + selected["component"])
        recovered.mkdir()
        native = Duplicacy(
            binary,
            tmp_path / ("control-" + selected["component"]),
            recovered,
            str(storage),
            selected["snapshot_id"],
            300,
        )
        native.initialize()
        native.command("restore", "-r", str(selected["revision"]))
        if selected["component"] == "database":
            assert verify(recovered)["facts"]["table_rows"] == {"empty_but_valid": 0, "readings": 1}
        elif selected["component"] == "raw_capture":
            assert (recovered / "capture.ndjson").read_bytes() == b'{"original":true}\n'
        else:
            assert any(
                json.loads(p.read_text())["type"] == "delivery" for p in recovered.glob("*.json")
            )


def test_native_unit_uses_common_owner_and_project_cadence(tmp_path):
    from shared.backup_units import rendered_units

    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/backup.json").read_text())["hosts"][socket.gethostname()]
    units = rendered_units(root / "config/backup.json")
    (service_name,) = (p.stem for p in root.glob("*.service.in"))
    timer_name = service_name.removesuffix(".service") + ".timer"
    service = units[service_name]
    timer = units[timer_name]
    assert "-m shared.backup_service --config " in service
    service_config = ConfigParser(interpolation=None)
    service_config.read_string(service)
    template = ConfigParser(interpolation=None)
    template.read(root / (service_name + ".in"))
    assert service_config["Unit"]["OnFailure"] == template["Unit"]["OnFailure"]
    assert f"TimeoutStartSec={config['cadence']['execution_timeout_seconds']}" in service
    assert f"OnCalendar={config['cadence']['on_calendar']}" in timer
    assert (
        f"RandomizedDelaySec={config['cadence']['randomized_delay_seconds']}" in timer.splitlines()
    )
    document = json.loads((root / "config/backup.json").read_text())
    cadence = document["hosts"][socket.gethostname()]["cadence"]
    cadence.update(
        execution_timeout_seconds=2713,
        on_calendar="*-*-* 10:17:00 UTC",
        randomized_delay_seconds=23,
    )
    (tmp_path / "config").mkdir()
    path = tmp_path / "config/backup.json"
    path.write_text(json.dumps(document))
    for name in units:
        (tmp_path / (name + ".in")).write_bytes((root / (name + ".in")).read_bytes())
    edited = rendered_units(path)
    service_config.read_string(edited[service_name])
    timer_config = ConfigParser(interpolation=None)
    timer_config.read_string(edited[timer_name])
    assert service_config["Service"]["TimeoutStartSec"] == "2713"
    assert timer_config["Timer"]["OnCalendar"] == "*-*-* 10:17:00 UTC"
    assert timer_config["Timer"]["RandomizedDelaySec"] == "23"


def test_capture_follows_only_the_collectors_sqlite_binding(tmp_path, monkeypatch):
    """Changing SQLITE_PATH must move the real captured DB without editing backup config."""
    import subprocess

    # Retain the formerly authoritative literal only as a deliberately stale input.
    host = {
        "environment_file": None,
        "components": {"database": {"source_path": str(tmp_path / "first.db")}},
    }
    config = tmp_path / "backup.json"
    config.write_text(json.dumps({"project": "enviroplus", "hosts": {socket.gethostname(): host}}))
    for name, count in (("first", 1), ("second", 2)):
        source = tmp_path / (name + ".db")
        connection = database(source)
        if count == 2:
            connection.execute("INSERT INTO readings VALUES ('second source')")
            connection.commit()
        connection.close()
        monkeypatch.setenv("SQLITE_PATH", str(source))
        output = tmp_path / name
        output.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sqlite_backup",
                "capture",
                "--config",
                str(config),
                "--component",
                "database",
                "--output-dir",
                str(output),
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        assert json.loads(result.stdout)["facts"]["table_rows"]["readings"] == count
        assert verify(output)["source"] == str(source)
