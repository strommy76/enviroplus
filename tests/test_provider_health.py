"""Actual SQLite observations at each health boundary; no provider/network stand-ins."""

import json
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import provider_health
from ambient_wx import ensure_schema
from provider_health import check

native_producer_state = provider_health.producer_state


@pytest.fixture(autouse=True)
def disabled_hardware_outside_provider_properties(monkeypatch):
    # Native activation is outside the existing external-provider SQL properties.
    monkeypatch.setattr(
        provider_health,
        "producer_state",
        lambda unit: {"LoadState": "loaded", "UnitFileState": "disabled"},
    )


def observations(tmp_path):
    policy = json.loads(
        (Path(__file__).resolve().parents[1] / "config/provider_health.json").read_text()
    )
    now = datetime(2026, 11, 19, 16, tzinfo=timezone.utc)
    path = tmp_path / "observations.db"
    with sqlite3.connect(path) as db:
        ensure_schema(db)
        db.execute("CREATE TABLE nws_weather (ts TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE epa_air_quality (ts TEXT PRIMARY KEY, local_time_zone TEXT)")
        db.execute(
            "INSERT INTO outdoor(ts,tempf) VALUES (?,75)", (now.strftime("%Y-%m-%d %H:%M:%S"),)
        )
        db.execute("INSERT INTO nws_weather VALUES (?)", (now.isoformat(),))
        db.execute("INSERT INTO epa_air_quality VALUES ('2026-11-19 10:00:00','EST')")
    return path, policy, now


def test_console_only_arrival_cannot_renew_outdoor_freshness(tmp_path):
    path, policy, now = observations(tmp_path)
    old = now - timedelta(seconds=policy["lanes"][0]["max_age_seconds"] + 1)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM outdoor")
        db.execute("INSERT INTO outdoor(ts,tempf) VALUES (?,75)", (old.isoformat(),))
        db.execute("INSERT INTO outdoor(ts,tempinf) VALUES (?,74)", (now.isoformat(),))
    results = check(path, policy, now)
    assert results[0]["problem"] == "observation_stale"
    assert all(result["problem"] is None for result in results[1:])


def test_broken_provider_query_keeps_the_other_observations(tmp_path):
    path, policy, now = observations(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE nws_weather")
    results = check(path, policy, now)
    assert results[1]["problem"] == "observation_unreadable"
    assert results[0]["problem"] is None
    assert results[2]["problem"] is None


def test_airnow_provider_local_time_is_not_utc(tmp_path):
    path, policy, now = observations(tmp_path)
    result = check(path, policy, now)[2]
    assert result["age_seconds"] == 3600  # 10 EST = 15 UTC, checked at16 UTC.
    assert result["problem"] is None


def test_missing_observation_is_not_fresh(tmp_path):
    path, policy, now = observations(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM nws_weather")
    assert check(path, policy, now)[1]["problem"] == "observation_missing"


def test_cli_reports_failure_and_preserves_all_lane_results(tmp_path, monkeypatch, capsys):
    """A missing real provider table must reach the exit/OnFailure boundary."""
    import provider_health

    path, _, _ = observations(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE nws_weather")
    monkeypatch.setenv("SQLITE_PATH", str(path))
    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps({"intervals": {"publish_s": 60, "display_refresh_s": 2}}))
    monkeypatch.setenv("CONFIG_PATH", str(capture))
    # Environment acquisition is outside the SQL/CLI-failure property.
    monkeypatch.setattr(provider_health, "load_env", lambda *args, **kwargs: None)
    assert provider_health.main() == 1
    results = json.loads(capsys.readouterr().out)
    assert len(results) == 4
    assert results[1]["problem"] == "observation_unreadable"


def test_clean_entrypoints_use_the_declared_shared_binding(tmp_path):
    """The real service import and documented renderer need no inherited shell path."""
    import os
    import shutil
    import subprocess
    import sys

    import shared

    root = Path(__file__).resolve().parents[1]
    # Actual documented sibling layout, including the selected Shared owner;
    # an arbitrary worktree parent need not carry the sibling checkout.
    (tmp_path / "shared").symlink_to(
        Path(shared.__file__).resolve().parent, target_is_directory=True
    )
    app = tmp_path / "enviroplus"
    app.mkdir()
    for source in root.glob("*.py"):
        shutil.copy(source, app)
    shutil.copytree(root / "config", app / "config")
    for template in root.glob("*.in"):
        shutil.copy(template, app)
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    from service_units import rendered_units

    service = rendered_units(app)["enviro_provider_health.service"]
    import shlex

    for line in service.splitlines():
        if line.startswith("Environment="):
            for binding in shlex.split(line.partition("=")[2]):
                key, value = binding.split("=", 1)
                environment[key] = value
    subprocess.run(
        [sys.executable, "-c", "import provider_health"], cwd=app, env=environment, check=True
    )
    environment["PYTHONPATH"] = ".."
    subprocess.run([sys.executable, "-m", "service_units"], cwd=app, env=environment, check=True)
    assert (app / "enviro_provider_health.timer").is_file()


@pytest.mark.parametrize(
    ("load_state", "file_state", "reading", "problem"),
    [
        ("loaded", "enabled", "missing", "observation_missing"),
        ("loaded", "enabled", "stale", "observation_stale"),
        ("loaded", "disabled", "missing", None),
        ("masked", "masked", "missing", None),
        ("loaded", "linked", "missing", None),
        ("not-found", "", "missing", None),
        ("query_error", "", "missing", "observation_unreadable"),
        ("loaded", "static", "missing", "observation_unreadable"),
    ],
)
def test_local_readings_follow_native_producer_authority(
    tmp_path, monkeypatch, load_state, file_state, reading, problem
):
    path, _, now = observations(tmp_path)
    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps({"intervals": {"publish_s": 60, "display_refresh_s": 2}}))
    monkeypatch.setenv("CONFIG_PATH", str(capture))
    policy = provider_health.load_policy(Path(__file__).resolve().parents[1])
    lane = next(item for item in policy["lanes"] if "producer_unit" in item)
    assert lane["max_age_seconds"] == 2 * 60 + policy["check_interval_seconds"] + 2
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE readings (ts TEXT PRIMARY KEY)")
        if reading == "stale":
            old = now - timedelta(seconds=lane["max_age_seconds"] + 1)
            db.execute("INSERT INTO readings VALUES (?)", (old.isoformat(),))

    def native(command, **kwargs):
        assert command == [
            "systemctl",
            "show",
            lane["producer_unit"],
            "--property=LoadState,UnitFileState",
        ]
        assert kwargs["check"] is True
        if load_state == "query_error":
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(
            command, 0, f"LoadState={load_state}\nUnitFileState={file_state}\n", ""
        )

    monkeypatch.setattr(provider_health, "producer_state", native_producer_state)
    monkeypatch.setattr(provider_health.subprocess, "run", native)
    results = check(path, policy, now)
    local = next(item for item in results if item["lane"] == lane["name"])
    assert local["problem"] == problem
    if load_state == "not-found":
        assert local["active"] is False
        assert local["detail"] == "producer not installed"
    elif file_state == "disabled":
        assert local["active"] is False
        assert local["detail"] == "producer disabled"
    elif load_state == "masked" or file_state == "linked":
        assert local["active"] is False
        assert local["detail"] == f"producer {file_state}"
    assert all(item["problem"] is None for item in results if item is not local)
