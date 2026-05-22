"""
--------------------------------------------------------------------------------
FILE:        test_nws_wx.py
PATH:        ~/projects/enviroplus/tests/test_nws_wx.py
DESCRIPTION: Tests for NWS observation freshness, station selection, and writes.

CHANGELOG:
2026-05-22 03:30      Codex      [Feature] Cover configured multi-station
                                      freshness selection, schema migration,
                                      and duplicate-aware NWS writes.
2026-05-22 03:30      Codex      [Fix] Include explicit shutdown cadence in
                                      NWS settings fixtures.
2026-05-22 03:30      Codex      [Fix] Cover bounded collection lookback
                                      configuration used for newest-observation
                                      selection.
--------------------------------------------------------------------------------
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import UTC, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nws_wx import (  # noqa: E402
    NoFreshObservationError,
    NwsSettings,
    _ensure_schema,
    _fetch,
    _select_observation,
    _write,
    load_settings,
)


def _settings() -> NwsSettings:
    return NwsSettings(
        api_base_url="https://api.weather.gov",
        stations=("STALE", "FRESH"),
        user_agent="test-agent",
        poll_s=600,
        shutdown_check_s=1,
        max_observation_age_s=7200,
        collection_lookback_s=21600,
        log_path="/tmp/enviroplus-test.log",
        sqlite_path="/tmp/enviroplus-test.db",
    )


def _properties(ts: str, *, temp_c: float = 27.0) -> dict:
    return {
        "timestamp": ts,
        "temperature": {"value": temp_c},
        "relativeHumidity": {"value": 50.0},
        "windSpeed": {"value": 10.0},
        "windGust": {"value": None},
        "windDirection": {"value": 90},
        "barometricPressure": {"value": 101_500.0},
        "visibility": {"value": 16_093.44},
        "dewpoint": {"value": 20.0},
        "heatIndex": {"value": None},
        "windChill": {"value": None},
        "precipitationLastHour": {"value": 0.0},
        "cloudLayers": [{"amount": "SCT"}],
        "textDescription": "Partly Cloudy",
    }


def test_load_settings_requires_configured_station_list(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "NWS_API_BASE_URL=https://api.weather.gov",
                "NWS_STATIONS=KCOF,KMLB",
                "NWS_USER_AGENT=test-agent",
                "NWS_POLL_S=600",
                "NWS_SHUTDOWN_CHECK_S=1",
                "NWS_MAX_OBSERVATION_AGE_S=7200",
                "NWS_COLLECTION_LOOKBACK_S=21600",
                "LOG_PATH=/tmp/enviro.log",
                "SQLITE_PATH=/tmp/enviro.db",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "NWS_API_BASE_URL",
        "NWS_STATIONS",
        "NWS_USER_AGENT",
        "NWS_POLL_S",
        "NWS_SHUTDOWN_CHECK_S",
        "NWS_MAX_OBSERVATION_AGE_S",
        "NWS_COLLECTION_LOOKBACK_S",
        "LOG_PATH",
        "SQLITE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(str(env_path))

    assert settings.stations == ("KCOF", "KMLB")
    assert settings.max_observation_age_s == 7200
    assert settings.collection_lookback_s == 21600


def test_select_observation_skips_stale_station_and_uses_fresh(caplog):
    settings = _settings()
    now = datetime(2026, 5, 22, 7, 15, tzinfo=UTC)

    def fetcher(_settings, station, _now_utc):
        if station == "STALE":
            return _properties("2026-05-21T15:55:00+00:00")
        return _properties("2026-05-22T07:00:00+00:00")

    with caplog.at_level(logging.WARNING):
        selected = _select_observation(
            settings,
            now_utc=now,
            logger=logging.getLogger("test_nws"),
            fetcher=fetcher,
        )

    assert selected["station_id"] == "FRESH"
    assert selected["ts"] == "2026-05-22T07:00:00+00:00"
    assert "STALE: stale timestamp" in caplog.text


def test_fetch_uses_collection_and_returns_newest_observation(monkeypatch):
    settings = _settings()
    now = datetime(2026, 5, 22, 7, 15, tzinfo=UTC)
    captured = {}

    class Response:
        def read(self):
            return json.dumps(
                {
                    "features": [
                        {"properties": _properties("2026-05-22T07:05:00+00:00")},
                        {"properties": _properties("2026-05-22T07:15:00+00:00")},
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("nws_wx.urllib.request.urlopen", fake_urlopen)

    selected = _fetch(settings, "KMLB", now)

    assert selected["timestamp"] == "2026-05-22T07:15:00+00:00"
    assert "/stations/KMLB/observations?" in captured["url"]
    assert "observations/latest" not in captured["url"]


def test_select_observation_raises_when_all_configured_stations_are_stale():
    settings = _settings()
    now = datetime(2026, 5, 22, 7, 15, tzinfo=UTC)

    def fetcher(_settings, _station, _now_utc):
        return _properties("2026-05-21T15:55:00+00:00")

    with pytest.raises(NoFreshObservationError, match="stale timestamp"):
        _select_observation(
            settings,
            now_utc=now,
            logger=logging.getLogger("test_nws"),
            fetcher=fetcher,
        )


def test_ensure_schema_adds_station_id_to_existing_table():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE nws_weather (ts TEXT PRIMARY KEY, temp_f REAL)")

    _ensure_schema(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(nws_weather)").fetchall()}
    assert "station_id" in columns


def test_write_reports_duplicate_as_not_inserted():
    conn = sqlite3.connect(":memory:")
    _ensure_schema(conn)
    logger = logging.getLogger("test_nws")
    row = {
        "ts": "2026-05-22T07:00:00+00:00",
        "station_id": "KMLB",
        "temp_f": 80.6,
        "humidity": 50.0,
        "wind_speed_mph": 6.2,
        "wind_gust_mph": None,
        "wind_direction": 90,
        "barometer_inhg": 29.97,
        "visibility_miles": 10.0,
        "dewpoint_f": 68.0,
        "heat_index_f": None,
        "wind_chill_f": None,
        "precip_1h_in": 0.0,
        "cloud_cover": "Partly Cloudy",
        "conditions": "Partly Cloudy",
    }

    assert _write(conn, logger, row) is True
    assert _write(conn, logger, row) is False
    count = conn.execute("SELECT COUNT(*) FROM nws_weather").fetchone()[0]
    assert count == 1
