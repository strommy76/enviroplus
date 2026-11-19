"""Actual SQLite observations at each health boundary; no provider/network stand-ins."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ambient_wx import ensure_schema
from provider_health import check


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
    # Environment acquisition is outside the SQL/CLI-failure property.
    monkeypatch.setattr(provider_health, "load_env", lambda *args, **kwargs: None)
    assert provider_health.main() == 1
    results = json.loads(capsys.readouterr().out)
    assert len(results) == 3
    assert results[1]["problem"] == "observation_unreadable"
